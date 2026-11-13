import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import outreach
import providers

STATIC = (Path(__file__).parent / "static").resolve()
TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
JOBS, POOL = {}, ThreadPoolExecutor(12)
JOBS_LOCK = threading.Lock()
MAX_JOBS = 50
MAX_REQUEST_BYTES = 1_048_576

SOCIAL = re.compile(
    r"facebook\.com|instagram\.com|linktr\.ee|wa\.me|twitter\.com|//x\.com|tiktok\.com|youtube\.com|linkedin\.com|threads\.net",
    re.I,
)

PARKED = re.compile(
    r"domain (is )?(for sale|parked|expired)|buy this domain|inquire about this domain|"
    r"domain may be for sale|this domain has expired|renew (your )?domain|"
    r"hugedomains|godaddy\.com/park|sedo\.com|dan\.com|afternic\.com|bodis\.com|parkingcrew|"
    r"account suspended|cgi-sys/suspendedpage\.cgi|cgi-sys/defaultwebpage\.cgi|"
    r"apache2 (ubuntu|debian) default page|welcome to nginx|iis windows server|cpanel default page",
    re.I,
)

MAILTO = re.compile(r"mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", re.I)
CF_EMAIL = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
REFRESH_URL = re.compile(
    r'<meta[^>]+http-equiv=[\'"]refresh[\'"][^>]+content=[\'"]\d+;\s*url=([^\'"]+)[\'"]', re.I
)
CONTACT_LINK = re.compile(
    r'href=[\'"]([^\'"]*(?:/contact|/about|contact-us|about-us|reach-us|get-in-touch|support|enquir|book|booking|find-us|location|privacy|gdpr|terms|impressum|imprint|legal|team|our-team)[^\'"]*)[\'"]',
    re.I,
)
SOC = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|facebook\.com|linktr\.ee|wa\.me|twitter\.com|x\.com|tiktok\.com|linkedin\.com)/[\w./?=&-]+",
    re.I,
)

DIRECTORIES = (
    "tripadvisor.", "booking.com", "hotels.com", "hotels.ng", "facebook.com", "instagram.com",
    "linkedin.com", "twitter.com", "x.com", "yellowpages.", "yelp.com", "expedia.com",
    "foursquare.com", "mapquest.com", "wikipedia.org", "wikidata.org", "jumia.",
    "vconnect.com", "finelib.com", "businesslist.com.ng", "connectnigeria.com",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

SSL_DEFAULT = ssl.create_default_context()
SSL_UNVERIFIED = ssl._create_unverified_context()


def decode_cf(cf_hex):
    try:
        k = int(cf_hex[:2], 16)
        return "".join([chr(int(cf_hex[i : i + 2], 16) ^ k) for i in range(2, len(cf_hex), 2)])
    except Exception:
        return ""


def fetch_page(url, timeout=8):
    """Fetches a URL trying HTTPS, unverified SSL, HTTP, and www fallback.
    Returns (html, final_url, note, is_working, status_code, elapsed_sec)"""
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    if path and not path.startswith("/"):
        path = "/" + path
    if parsed.query:
        path += "?" + parsed.query

    variations = [
        f"https://{netloc}{path}",
        f"http://{netloc}{path}",
    ]
    if not netloc.startswith("www.") and "." in netloc:
        variations.append(f"https://www.{netloc}{path}")
        variations.append(f"http://www.{netloc}{path}")
    elif netloc.startswith("www."):
        non_www = netloc[4:]
        variations.append(f"https://{non_www}{path}")

    last_exc = None
    for target in variations:
        for use_unverified in (False, True):
            t0 = time.time()
            try:
                ctx = SSL_UNVERIFIED if use_unverified else SSL_DEFAULT
                req = urllib.request.Request(target, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    elapsed = round(time.time() - t0, 2)
                    code = resp.getcode()
                    html = resp.read(350000).decode("utf-8", "ignore")
                    final_url = resp.geturl() or target
                    note = "Loads fine" + (" (SSL warning)" if use_unverified else "")
                    return html, final_url, note, True, code, elapsed
            except urllib.error.HTTPError as e:
                elapsed = round(time.time() - t0, 2)
                if e.code in (401, 403, 429):
                    return "", target, f"HTTP {e.code} (Protected / Active)", True, e.code, elapsed
                last_exc = e
                break
            except ssl.SSLCertVerificationError as e:
                last_exc = e
                if not use_unverified:
                    continue
                break
            except Exception as e:
                last_exc = e
                break

    if isinstance(last_exc, urllib.error.HTTPError):
        return "", url, f"HTTP {last_exc.code}", False, last_exc.code, 0.0

    err_str = str(getattr(last_exc, "reason", last_exc))
    if "getaddrinfo failed" in err_str or "11001" in err_str:
        return "", url, "DNS lookup failed (Domain not found)", False, None, 0.0
    if "10061" in err_str or "refused" in err_str.lower():
        return "", url, "Connection refused (Server down)", False, None, 0.0
    if "timed out" in err_str.lower() or "10060" in err_str:
        return "", url, "Connection timed out", False, None, 0.0
    return "", url, f"{type(last_exc).__name__}: {err_str[:45]}", False, None, 0.0


def discover_online(biz_name, city):
    """Searches web via outreach engine to discover candidate website, socials, and snippet emails."""
    if not biz_name:
        return "", [], []
    try:
        q = f'"{biz_name}" {city}'.strip()
        html = outreach.search_web_snippets(q, timeout=4)
        if not html:
            return "", [], []

        snippet_emails = outreach.extract_emails_from_text(html)
        uddg_links = re.findall(r'href=["\'](?:https?:)?//duckduckgo\.com/l/\?uddg=([^"\'&]+)', html)
        links = [urllib.parse.unquote(u) for u in uddg_links]
        if not links:
            links = re.findall(
                r'<a[^>]+class=[\'"][^\'"]*result__url[^\'"]*[\'"][^>]+href=[\'"]([^\'"]+)[\'"]', html
            )
        if not links:
            links = re.findall(r'href=[\'"](https?://[^\'"\s>]+)[\'"]', html)

        candidate_site = None
        candidate_soc = []
        for link in links:
            l_lower = link.lower()
            if any(k in l_lower for k in ("duckduckgo.com", "bing.com", "google.com", "microsoft.com", "yahoo.com")):
                continue
            if SOCIAL.search(l_lower):
                clean_s = link.split("?")[0].rstrip("/")
                if "/p/" not in clean_s and "/posts/" not in clean_s and clean_s not in candidate_soc:
                    candidate_soc.append(clean_s)
            elif not any(d in l_lower for d in DIRECTORIES):
                if not candidate_site:
                    candidate_site = link
        return candidate_site or "", candidate_soc, snippet_emails
    except Exception:
        return "", [], []


def query_wikidata(qid):
    """Fetches official website and email from Wikidata claims P856 and P968."""
    if not qid:
        return "", ""
    try:
        url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&format=json&props=claims"
        req = urllib.request.Request(url, headers={"User-Agent": "LeadFinder/1.1"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.load(r)
            entity = data.get("entities", {}).get(qid, {})
            claims = entity.get("claims", {})
            website = (
                claims.get("P856", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value", "")
            )
            email = (
                claims.get("P968", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value", "")
            )
            if email.startswith("mailto:"):
                email = email[7:]
            return website, email
    except Exception:
        return "", ""


def extract_page_emails(html):
    raw_mails = []
    raw_mails.extend(MAILTO.findall(html))
    for cf_hex in CF_EMAIL.findall(html):
        decoded = decode_cf(cf_hex)
        if decoded:
            raw_mails.append(decoded)
    raw_mails.extend(outreach.extract_emails_from_text(html))
    return raw_mails


def check_site(
    url,
    biz_name="",
    city="",
    wikidata_id="",
    category="",
    existing_socials=(),
    existing_phone="",
    existing_email="",
    settings=None,
):
    """
    Performs full website verification, live technical/conversion audit, and aggressive multi-channel email/social hunting.
    Returns (status, note, socials, emails_str, verified_url, audit_issues, discovered_phone, email_guessed).
    """
    s = settings or outreach.get_settings()
    url = (url or "").strip()
    socials = list(existing_socials or [])
    emails = outreach.filter_valid_emails((existing_email or "").split(","))
    discovered_phone = existing_phone or ""

    # 1. Check Wikidata if available
    if not url and wikidata_id:
        wiki_web, wiki_mail = query_wikidata(wikidata_id)
        if wiki_web:
            url = wiki_web
        if wiki_mail:
            emails.append(wiki_mail)

    # 2. If still no URL, run online discovery
    if not url:
        discovered_url, discovered_soc, snippet_mails = discover_online(biz_name, city)
        socials.extend(discovered_soc)
        emails.extend(snippet_mails)
        if discovered_url:
            url = discovered_url

    # 3. If no website OR social-only URL: aggressively hunt emails, socials & phone from search snippets & directories
    if not url or SOCIAL.search(url):
        if url and SOCIAL.search(url):
            socials.append(url)
        hunted_mails, hunted_soc, hunted_phone = outreach.hunt_emails_without_website(
            biz_name, city, socials, discovered_phone
        )
        emails.extend(hunted_mails)
        socials.extend(hunted_soc)
        if hunted_phone and not discovered_phone:
            discovered_phone = hunted_phone

        clean_mails = outreach.filter_valid_emails(emails)
        clean_socs = list(dict.fromkeys(socials))[:5]
        email_str = ", ".join(clean_mails[:3])

        if clean_socs or (url and SOCIAL.search(url)):
            return (
                "social_only",
                "Social profile only — needs a dedicated website",
                clean_socs,
                email_str,
                url if (url and SOCIAL.search(url)) else (clean_socs[0] if clean_socs else ""),
                ["No Dedicated Website", "Relying on Social Links Only"],
                discovered_phone,
                False,
            )
        return (
            "no_website",
            "No website found — prime web design prospect",
            [],
            email_str,
            "",
            ["Zero Web Presence", "Missing Google Maps Website"],
            discovered_phone,
            False,
        )

    # 4. Fetch and verify regular website
    html, final_url, note, is_working, code, elapsed_sec = fetch_page(url)

    if not is_working:
        # Even when website is broken, hunt for their email & socials so we can pitch them the fix!
        hunted_mails, hunted_soc, hunted_phone = outreach.hunt_emails_without_website(
            biz_name, city, socials, discovered_phone
        )
        emails.extend(hunted_mails)
        socials.extend(hunted_soc)
        if hunted_phone and not discovered_phone:
            discovered_phone = hunted_phone
        clean_mails = outreach.filter_valid_emails(emails)
        return (
            "broken",
            note,
            list(dict.fromkeys(socials))[:5],
            ", ".join(clean_mails[:3]),
            url,
            [f"Broken Site ({note})"],
            discovered_phone,
            False,
        )

    # Check for HTML meta-refresh redirect (1 hop)
    refresh_match = REFRESH_URL.search(html)
    if refresh_match:
        redirect_target = refresh_match.group(1).strip()
        if not redirect_target.startswith("http"):
            redirect_target = urllib.parse.urljoin(final_url, redirect_target)
        r_html, r_final, r_note, r_working, r_code, r_elapsed = fetch_page(redirect_target, timeout=5)
        if r_working and r_html:
            html, final_url, note, code, elapsed_sec = r_html, r_final, r_note, r_code, r_elapsed

    # Check for Parked Domain / For Sale / Default server page
    if PARKED.search(html):
        hunted_mails, hunted_soc, hunted_phone = outreach.hunt_emails_without_website(
            biz_name, city, socials, discovered_phone
        )
        emails.extend(hunted_mails)
        socials.extend(hunted_soc)
        clean_mails = outreach.filter_valid_emails(emails)
        return (
            "broken",
            "Domain parked or for sale",
            list(dict.fromkeys(socials))[:5],
            ", ".join(clean_mails[:3]),
            final_url,
            ["Expired / Parked Domain"],
            discovered_phone or hunted_phone,
            False,
        )

    is_protected_response = code in (401, 403, 429) and not html.strip()
    if not is_protected_response and len(html.strip()) < 80:
        clean_mails = outreach.filter_valid_emails(emails)
        return (
            "broken",
            "Empty page response",
            list(dict.fromkeys(socials))[:5],
            ", ".join(clean_mails[:3]),
            final_url,
            ["Blank / Broken Page"],
            discovered_phone,
            False,
        )

    # 5. Extract emails from working homepage
    raw_mails = extract_page_emails(html) if html else []
    if html:
        socials.extend(SOC.findall(html))

    # 6. If no emails on homepage, crawl up to 4 high-value subpages (/contact, /about, /privacy, /impressum, /terms, /booking, /enquiries)
    if html and not raw_mails and not emails:
        contact_links = list(dict.fromkeys(CONTACT_LINK.findall(html)))[:4]
        for sub_raw in contact_links:
            sub_url = sub_raw.strip()
            if not sub_url.startswith("http"):
                sub_url = urllib.parse.urljoin(final_url, sub_url)
            if not sub_url.lower().startswith(("http://", "https://")):
                continue
            try:
                sub_req = urllib.request.Request(sub_url, headers=HEADERS)
                with urllib.request.urlopen(sub_req, timeout=3.5, context=SSL_UNVERIFIED) as s_resp:
                    s_html = s_resp.read(250000).decode("utf-8", "ignore")
                    sub_emails = extract_page_emails(s_html)
                    raw_mails.extend(sub_emails)
                    socials.extend(SOC.findall(s_html))
                    if sub_emails:
                        break
            except Exception:
                pass

    valid_emails = outreach.filter_valid_emails(emails + raw_mails)

    # 7. If still no email on site, run DuckDuckGo domain site search (site:{domain} email)
    if not valid_emails:
        site_search_mails = outreach.hunt_site_search_emails(final_url)
        if site_search_mails:
            valid_emails.extend(site_search_mails)

    # 8. Optional Hunter.io domain search if still no email
    if not valid_emails and s.get("hunter_api_key"):
        hunter_mails = outreach.query_hunter_domain(final_url, s["hunter_api_key"])
        valid_emails.extend(hunter_mails)

    # 9. If still no email on site, search snippets for business email / @gmail.com
    if not valid_emails:
        hunted_mails, hunted_soc, hunted_phone = outreach.hunt_emails_without_website(
            biz_name, city, socials, discovered_phone
        )
        valid_emails = outreach.filter_valid_emails(valid_emails + hunted_mails)
        socials.extend(hunted_soc)
        if hunted_phone and not discovered_phone:
            discovered_phone = hunted_phone

    # 10. If still no email and site is on a genuine custom business domain, derive candidate domain emails (marked unverified)
    email_guessed = False
    if not valid_emails:
        candidates = outreach.derive_domain_emails(final_url, category=category)
        if candidates:
            valid_emails.extend(candidates[:2])
            email_guessed = True

    # 11. Run Live Technical, SEO & Conversion Audit on the working website (skip HTML checks on WAF/bot-blocked responses)
    if is_protected_response:
        audit_issues = [f"Site Protected (HTTP {code} — Manual Review)"]
    else:
        audit_issues = outreach.audit_working_website(html, final_url, note, elapsed_sec, category)

    clean_socials = list(dict.fromkeys(socials))[:5]
    email_str = ", ".join(valid_emails[:3])

    return "working", note, clean_socials, email_str, final_url, audit_issues, discovered_phone, email_guessed


def enrich(job, b, settings):
    status, note, soc, mail, verified_url, audit_issues, disc_phone, email_guessed = check_site(
        b["website"],
        biz_name=b.get("name", ""),
        city=b.get("city", ""),
        wikidata_id=b.get("wikidata_id", ""),
        category=b.get("category", ""),
        existing_socials=b.get("socials", ()),
        existing_phone=b.get("phone", ""),
        existing_email=b.get("email", ""),
        settings=settings,
    )
    b["site_status"] = status
    b["site_note"] = note
    b["audit_issues"] = audit_issues
    if verified_url and not b["website"]:
        b["website"] = verified_url
    if disc_phone and not b.get("phone"):
        b["phone"] = disc_phone
    b["socials"] = list(dict.fromkeys((b.get("socials") or []) + soc))[:5]
    b["email"] = mail
    b["email_guessed"] = bool(mail and email_guessed)
    b["email_verified"] = bool(mail and not email_guessed)

    # Resolve best 1-click DM link (Instagram / Facebook / X / LinkedIn / WhatsApp)
    b["dm_info"] = outreach.resolve_dm_channel(b["socials"], b.get("phone", ""))
    b["lead_score"] = outreach.calculate_lead_score(b)

    # Generate tailored outreach writeup (email subject + body + short social/WhatsApp DM)
    pitch = outreach.generate_ai_outreach(b, settings)
    b["outreach_subject"] = pitch["subject"]
    b["outreach_body"] = pitch["body"]
    b["outreach_dm"] = pitch["dm"]

    # Check if already emailed or if auto-send is enabled (never auto-send to unverified/guessed emails)
    primary_email = (b["email"] or "").split(",")[0].strip().lower()
    b["email_status"] = ""
    b["email_status_note"] = ""

    if primary_email:
        if outreach.is_email_already_sent(primary_email):
            b["email_status"] = "already_sent"
            b["email_status_note"] = f"Previously sent to {primary_email}"
        elif b["email_guessed"]:
            b["email_status"] = "guessed"
            b["email_status_note"] = "Suggested domain email (unverified) — skipped by auto-send"
        elif settings.get("auto_send_email"):
            res = outreach.send_smtp_email(
                primary_email,
                b["outreach_subject"],
                b["outreach_body"],
                biz_name=b.get("name", ""),
                force=False,
            )
            b["email_status"] = res["status"]
            b["email_status_note"] = res["message"]
            if res.get("ok") and res["status"] in ("sent", "simulated"):
                with job["lock"]:
                    job["sent_count"] = job.get("sent_count", 0) + 1

    with job["lock"]:
        job["results"].append(b)


def run(job, p):
    def set_msg(m):
        with job["lock"]:
            job["msg"] = m

    try:
        settings = outreach.get_settings()
        seen = set()
        for b in providers.PROVIDERS[p["provider"]]["fn"](p, set_msg):
            if b["id"] in seen:
                continue
            seen.add(b["id"])
            with job["lock"]:
                job["found"] = len(seen)
                job["futs"].append(POOL.submit(enrich, job, b, settings))
        set_msg("Hunting emails, auditing sites & preparing pitches")
        with job["lock"]:
            futs = list(job["futs"])
        for f in futs:
            try:
                f.result()
            except Exception:
                pass
        set_msg("Done")
    except Exception as e:
        err_msg = str(e)
        if "10060" in err_msg:
            err_msg = "Network timeout (WinError 10060): Unable to reach map server. Please check your internet connection."
        with job["lock"]:
            job["error"] = err_msg
    finally:
        with job["lock"]:
            job["done"] = True


def _prune_old_jobs():
    with JOBS_LOCK:
        if len(JOBS) < MAX_JOBS:
            return
        completed_ids = [
            jid for jid, j in sorted(JOBS.items(), key=lambda kv: kv[1].get("created_at", 0))
            if j.get("done")
        ]
        for jid in completed_ids[: max(1, len(JOBS) - MAX_JOBS + 1)]:
            JOBS.pop(jid, None)


class H(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def read_json(self):
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            return {}
        length = int(raw_len)
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Invalid Content-Length")
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/providers":
            return self.reply(
                200,
                [{"id": k, "label": v["label"], "key": v["key"]} for k, v in providers.PROVIDERS.items()],
            )
        if u.path == "/api/settings":
            s = outreach.get_public_settings()
            ledger = outreach.get_sent_ledger()
            return self.reply(200, {"settings": s, "sent_total": len(ledger)})
        if u.path.startswith("/api/job/"):
            jid = u.path.split("/")[-1]
            with JOBS_LOCK:
                j = JOBS.get(jid)
            if not j:
                return self.reply(404, {"error": "Unknown job"})
            try:
                since = int(urllib.parse.parse_qs(u.query).get("since", [0])[0])
                if since < 0:
                    raise ValueError("negative")
            except ValueError:
                return self.reply(400, {"error": "Invalid since parameter"})
            with j["lock"]:
                payload = {k: j[k] for k in ("msg", "found", "done", "error", "sent_count")} | {
                    "results": list(j["results"][since:])
                }
            return self.reply(200, payload)
        f = (STATIC / ("index.html" if u.path == "/" else u.path.lstrip("/"))).resolve()
        if f.is_file() and STATIC in f.parents:
            return self.reply(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
        self.reply(404, {"error": "Not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            p = self.read_json()
        except Exception as e:
            return self.reply(400, {"error": f"Invalid JSON: {e}"})
        if not isinstance(p, dict):
            return self.reply(400, {"error": "JSON body must be an object"})

        if u.path == "/api/settings":
            updated = outreach.save_settings(p)
            ledger = outreach.get_sent_ledger()
            return self.reply(200, {"ok": True, "settings": outreach.get_public_settings(updated), "sent_total": len(ledger)})

        if u.path == "/api/send-email":
            res = outreach.send_smtp_email(
                p.get("email", ""),
                p.get("subject", ""),
                p.get("body", ""),
                biz_name=p.get("name", ""),
                force=bool(p.get("force", True)),
            )
            return self.reply(200 if res.get("ok") else 400, res)

        if u.path == "/api/test-smtp":
            if isinstance(p.get("settings"), dict):
                outreach.save_settings(p["settings"])
            s = outreach.get_settings()
            target = (p.get("to") or s.get("smtp_email") or "").strip()
            if not target:
                return self.reply(400, {"ok": False, "message": "Enter your SMTP Email first."})
            res = outreach.send_smtp_email(
                target,
                "LeadFinder SMTP Test — Connected!",
                f"Hi {s.get('sender_name', 'there')},\n\nYour LeadFinder auto-outreach SMTP connection is working properly!\n\n— LeadFinder",
                biz_name="SMTP Test",
                force=True,
            )
            return self.reply(200 if res.get("ok") else 400, res)

        if u.path == "/api/regenerate-pitch":
            lead = p.get("lead") or {}
            angle = p.get("angle") or "auto"
            use_ai = bool(p.get("use_ai", False))
            pitch = (
                outreach.generate_ai_outreach(lead, angle_override=angle)
                if use_ai
                else outreach.generate_outreach(lead, angle_override=angle)
            )
            return self.reply(200, {"ok": True, **pitch})

        if u.path == "/api/start":
            provider_id = (p.get("provider") or "").strip()
            city = (p.get("city") or "").strip()
            category = (p.get("category") or "").strip()
            if provider_id not in providers.PROVIDERS:
                return self.reply(400, {"error": f"Unknown provider: {provider_id}"})
            if not city or not category:
                return self.reply(400, {"error": "Both 'city' and 'category' are required."})

            _prune_old_jobs()
            jid = uuid.uuid4().hex[:8]
            job = {
                "results": [],
                "futs": [],
                "msg": "Starting",
                "found": 0,
                "sent_count": 0,
                "done": False,
                "error": None,
                "created_at": time.time(),
                "lock": threading.Lock(),
            }
            with JOBS_LOCK:
                JOBS[jid] = job
            threading.Thread(target=run, args=(job, p), daemon=True).start()
            return self.reply(200, {"id": jid})

        return self.reply(404, {"error": "Not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"LeadFinder running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
