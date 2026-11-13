"""
LeadFinder Outreach, Deep Email Hunting, Website Audit & Auto-Mailer Engine.
Zero external dependencies — uses only Python 3.10+ standard library.
"""
import html as html_lib
import json
import os
import re
import smtplib
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

DATA_DIR = (Path(__file__).parent / "data").resolve()
SETTINGS_FILE = DATA_DIR / "settings.json"
SENT_LOG_FILE = DATA_DIR / "sent_emails.json"
ENV_FILE = Path(__file__).parent / ".env"

_LOCK = threading.Lock()
_INFLIGHT_EMAILS = set()

SECRET_KEYS = ("smtp_password", "hunter_api_key", "gemini_api_key", "groq_api_key")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SSL_UNVERIFIED = ssl._create_unverified_context()

DEFAULT_SETTINGS = {
    "sender_name": "Frank Oge",
    "sender_role": "Founder & Lead Engineer",
    "sender_company": "Hackverse Technologies",
    "sender_portfolio": "https://frankoge.com",
    "sender_company_url": "https://hackversetechnologies.vercel.app",
    "sender_phone": "",
    "pitch_angle": "auto",  # auto | web_design | ai_automation | local_seo | ads_funnel | redesign
    "custom_offer": "",
    "smtp_email": "",
    "smtp_password": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "auto_send_email": False,
    "dry_run": False,
    "hunter_api_key": "",
    "gemini_api_key": "",
    "groq_api_key": "",
}

# Regex patterns for deep email & obfuscated email extraction
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.I)
OBFUSCATED_EMAIL_RE = re.compile(
    r"\b([a-zA-Z][a-zA-Z0-9_.+-]{1,35})\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+|&#64;|&amp;#64;)\s*([a-zA-Z0-9-]+)\s*(?:\[dot\]|\(dot\)|\{dot\}|\s+dot\s+|\.)\s*([a-zA-Z]{2,10})\b",
    re.I,
)
JSON_LD_EMAIL_RE = re.compile(r'["\'](?:email|telephone|emailAddress)["\']\s*:\s*["\']([^"\']+)["\']', re.I)
ATTR_EMAIL_RE = re.compile(r'(?:data-email|data-mail|data-contact|data-address|data-to|data-cfemail)\s*=\s*["\']([^"\']+)["\']', re.I)
PHONE_INTL_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3,4}[\s.-]?\d{4}")

BAD_EMAIL_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2", ".ttf", ".ico", ".mp4", ".pdf"
)
BAD_EMAIL_SUBSTRINGS = (
    "example.com", "example.org", "yourdomain", "domain.com", "email.com", "sentry.io",
    "wixpress.com", "wix.com", "squarespace.com", "wordpress.org", "w3.org", "schema.org",
    "duckduckgo.com", "bing.com", "google.com", "facebook.com", "instagram.com",
    "cloudflare.com", "bootstrap@", "noreply@", "no-reply@", "donotreply@", "postmaster@",
    "hostmaster@", "webmaster@example", "user@", "test@", "name@", "firstname@", "yourname@"
)


def _load_dotenv():
    """Loads optional .env file values as defaults if present."""
    env_vals = {}
    if ENV_FILE.is_file():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vals[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env_vals


def _atomic_write_json(path, data):
    """Writes JSON atomically via a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def _read_settings_unlocked():
    """Returns merged settings from defaults, .env/env vars, and settings.json."""
    s = dict(DEFAULT_SETTINGS)
    env = _load_dotenv()
    env_map = {
        "SENDER_NAME": "sender_name",
        "SENDER_ROLE": "sender_role",
        "SENDER_PORTFOLIO": "sender_portfolio",
        "SENDER_COMPANY": "sender_company",
        "SENDER_COMPANY_URL": "sender_company_url",
        "SENDER_PHONE": "sender_phone",
        "PITCH_ANGLE": "pitch_angle",
        "CUSTOM_OFFER": "custom_offer",
        "SMTP_EMAIL": "smtp_email",
        "SMTP_APP_PASSWORD": "smtp_password",
        "SMTP_HOST": "smtp_host",
        "SMTP_PORT": "smtp_port",
        "AUTO_SEND_EMAIL": "auto_send_email",
        "DRY_RUN": "dry_run",
        "HUNTER_API_KEY": "hunter_api_key",
        "GEMINI_API_KEY": "gemini_api_key",
        "GROQ_API_KEY": "groq_api_key",
    }
    for ek, sk in env_map.items():
        val = env.get(ek) or os.environ.get(ek)
        if val is not None and val != "":
            if isinstance(s[sk], bool):
                s[sk] = val.lower() in ("1", "true", "yes", "on")
            elif isinstance(s[sk], int):
                try:
                    s[sk] = int(val)
                except ValueError:
                    pass
            else:
                s[sk] = val

    if SETTINGS_FILE.is_file():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for k, v in saved.items():
                    if k in DEFAULT_SETTINGS:
                        s[k] = v
        except Exception:
            pass
    return s


def get_settings():
    """Thread-safe merged settings reader."""
    with _LOCK:
        return _read_settings_unlocked()


def get_public_settings(settings=None):
    """Returns settings safe to expose to the browser (secret values redacted)."""
    s = dict(settings or get_settings())
    configured = {k: bool(s.get(k)) for k in SECRET_KEYS}
    for k in SECRET_KEYS:
        s[k] = ""
    s["configured_secrets"] = configured
    return s


def save_settings(new_settings):
    """Persists updated settings to data/settings.json without leaking or wiping saved secrets."""
    with _LOCK:
        saved = {}
        if SETTINGS_FILE.is_file():
            try:
                loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    saved = loaded
            except Exception:
                saved = {}

        for k in DEFAULT_SETTINGS:
            if k in SECRET_KEYS:
                if new_settings.get(f"clear_{k}"):
                    saved[k] = ""
                elif k in new_settings:
                    val = str(new_settings[k] or "").strip()
                    if val:
                        saved[k] = val
                continue

            if k in new_settings:
                val = new_settings[k]
                if isinstance(DEFAULT_SETTINGS[k], bool):
                    saved[k] = bool(val) if not isinstance(val, str) else val.lower() in ("1", "true", "yes", "on")
                elif isinstance(DEFAULT_SETTINGS[k], int):
                    try:
                        saved[k] = int(val)
                    except (ValueError, TypeError):
                        saved[k] = DEFAULT_SETTINGS[k]
                else:
                    saved[k] = str(val or "").strip()

        _atomic_write_json(SETTINGS_FILE, saved)
        return _read_settings_unlocked()


def _read_sent_ledger_unlocked():
    if SENT_LOG_FILE.is_file():
        try:
            data = json.loads(SENT_LOG_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def get_sent_ledger():
    """Returns dict of {email_lower: {biz_name, sent_at, subject}}."""
    with _LOCK:
        return _read_sent_ledger_unlocked()


def mark_email_sent(email_addr, biz_name="", subject=""):
    """Records an email in the persistent single-send ledger."""
    email_key = (email_addr or "").strip().lower()
    if not email_key:
        return
    with _LOCK:
        ledger = _read_sent_ledger_unlocked()
        ledger[email_key] = {
            "biz_name": biz_name,
            "subject": subject,
            "sent_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _atomic_write_json(SENT_LOG_FILE, ledger)


def is_email_already_sent(email_addr):
    email_key = (email_addr or "").strip().lower()
    if not email_key:
        return False
    with _LOCK:
        return email_key in _read_sent_ledger_unlocked()


def extract_emails_from_text(text):
    """Extracts standard, schema-embedded, attribute-based, and obfuscated emails from arbitrary HTML/text."""
    if not text:
        return []
    
    found = []

    # 1. First, extract from mailto links directly: href="mailto:..."
    found.extend(re.findall(r'href=[\'"]mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text, re.I))

    # 2. Extract JSON-LD structured schema emails
    for m in JSON_LD_EMAIL_RE.findall(text):
        if "@" in m:
            clean_m = m.replace("mailto:", "").strip()
            found.extend(EMAIL_RE.findall(clean_m))

    # 3. Extract explicit data attributes (data-email, data-mail, data-contact)
    for m in ATTR_EMAIL_RE.findall(text):
        if "@" in m and not m.startswith("%"):
            found.extend(EMAIL_RE.findall(m))

    # 4. Strip search engine links & URL queries (?q=... or &q=...) to prevent extracting URL-encoded search parameters
    clean_text = re.sub(r'href=[\'"][^\'"]*[\'"]', ' ', text)
    clean_text = re.sub(r'[?&][a-zA-Z0-9_]+=[^\s"\'<>]+', ' ', clean_text)
    clean_text = re.sub(r'%[0-9a-fA-F]{2}', ' ', clean_text)
    unescaped = html_lib.unescape(clean_text)

    # 5. Standard plaintext emails in text
    found.extend(EMAIL_RE.findall(unescaped))

    # 6. Obfuscated emails in text (e.g. "contact [at] domain [dot] com")
    for m in OBFUSCATED_EMAIL_RE.finditer(unescaped):
        reconstructed = f"{m.group(1)}@{m.group(2)}.{m.group(3)}"
        found.append(reconstructed)

    return filter_valid_emails(found)


def filter_valid_emails(raw_list):
    """Filters out junk, asset filenames, URL encoding artifacts, and system emails."""
    valid = []
    for m in raw_list:
        m = m.strip().lower().strip(".,;:()[]<>\"'\\/?#%&")
        if len(m) < 6 or len(m) > 85:
            continue
        if any(m.endswith(ext) for ext in BAD_EMAIL_EXTS):
            continue
        if any(bad in m for bad in BAD_EMAIL_SUBSTRINGS):
            continue
        parts = m.split("@")
        if len(parts) != 2:
            continue
        local, domain = parts
        if not local or not domain or "." not in domain:
            continue
        # Username cannot be pure numbers or less than 2 chars (e.g. 22@, 123@)
        if local.isdigit() or len(local) < 2:
            continue
        # Local part must start with alphanumeric letter
        if not local[0].isalnum():
            continue
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) < 2 or tld.isdigit():
            continue
        if m not in valid:
            valid.append(m)
    return valid


_SEARCH_LOCK = threading.Lock()
_LAST_SEARCH_TIME = 0.0


def search_web_snippets(query, timeout=4):
    """
    Executes a web search with rate-limiting lock and multi-engine fallback (DDG HTML -> DDG Lite -> Bing).
    Prevents 403 / bot-check blocks when worker threads search concurrently.
    Returns raw HTML containing search snippets and links.
    """
    global _LAST_SEARCH_TIME
    with _SEARCH_LOCK:
        elapsed = time.time() - _LAST_SEARCH_TIME
        if elapsed < 0.35:
            time.sleep(0.35 - elapsed)
        _LAST_SEARCH_TIME = time.time()

    # 1. Try DuckDuckGo HTML
    try:
        data = urllib.parse.urlencode({"q": query}).encode()
        req = urllib.request.Request(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers={
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://html.duckduckgo.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_UNVERIFIED) as resp:
            html = resp.read(250000).decode("utf-8", "ignore")
            if "anomaly-modal" not in html and len(html) > 1000:
                return html
    except Exception:
        pass

    # 2. Try DuckDuckGo Lite (no JavaScript, separate endpoint, less strict rate-limiting)
    try:
        data = urllib.parse.urlencode({"q": query}).encode()
        req = urllib.request.Request(
            "https://lite.duckduckgo.com/lite/",
            data=data,
            headers={
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://lite.duckduckgo.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_UNVERIFIED) as resp:
            html = resp.read(250000).decode("utf-8", "ignore")
            if len(html) > 1000:
                return html
    except Exception:
        pass

    # 3. Fallback to Bing Search HTML (rich local business snippets with phone & emails)
    try:
        b_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            b_url,
            headers={
                **HEADERS,
                "Referer": "https://www.bing.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_UNVERIFIED) as resp:
            return resp.read(250000).decode("utf-8", "ignore")
    except Exception:
        pass

    return ""


def hunt_site_search_emails(website_url):
    """
    Searches indexed search snippets for the specific domain to catch emails listed on subpages, PDFs, or menus.
    Extremely effective when a custom website hides its contact email behind a Javascript form.
    """
    if not website_url:
        return []
    try:
        parsed = urllib.parse.urlparse(website_url if "://" in website_url else "https://" + website_url)
        domain = parsed.netloc.lower().lstrip("www.")
        if not domain or "." not in domain:
            return []
        for bad in ("wixsite.com", "wordpress.com", "squarespace.com", "facebook.com", "instagram.com", "linktr.ee"):
            if bad in domain:
                return []
        q = f'site:{domain} email OR contact OR enquiries OR hello OR "@"'
        html = search_web_snippets(q, timeout=4)
        return filter_valid_emails(extract_emails_from_text(html))
    except Exception:
        return []


def derive_domain_emails(website_url, category=""):
    """
    Generates high-probability candidate domain emails (info@, orders@, bookings@, contact@)
    for genuine custom business domains when no direct plaintext email was listed on page.
    """
    if not website_url:
        return []
    try:
        parsed = urllib.parse.urlparse(website_url if "://" in website_url else "https://" + website_url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        if not netloc or "." not in netloc:
            return []
        for bad in ("wixsite.com", "wordpress.com", "squarespace.com", "weebly.com", "godaddysites.com", "myshopify.com", "facebook.com", "instagram.com"):
            if bad in netloc:
                return []

        cat_low = (category or "").lower()
        candidates = []

        if any(w in cat_low for w in ("bakery", "baker", "pastry", "restaurant", "cafe", "food", "catering")):
            candidates.extend([f"orders@{netloc}", f"info@{netloc}", f"hello@{netloc}"])
        elif any(w in cat_low for w in ("salon", "hair", "beauty", "barber", "spa", "massage")):
            candidates.extend([f"bookings@{netloc}", f"info@{netloc}", f"appointments@{netloc}"])
        elif any(w in cat_low for w in ("clinic", "dentist", "dental", "doctor", "health", "physio")):
            candidates.extend([f"info@{netloc}", f"reception@{netloc}", f"enquiries@{netloc}"])
        else:
            candidates.extend([f"info@{netloc}", f"contact@{netloc}", f"hello@{netloc}"])

        if netloc.endswith(".uk") or netloc.endswith(".co.uk"):
            if f"enquiries@{netloc}" not in candidates:
                candidates.insert(0, f"enquiries@{netloc}")

        return candidates
    except Exception:
        return []


def hunt_emails_without_website(biz_name, city, socials=(), existing_phone=""):
    """
    Aggressively hunts for a business's email, phone, and social links even when they have NO website.
    Uses:
    1. Multi-engine search for "{biz_name}" "{city}" email / @gmail.com / contact snippets
    2. Public social/directory page scraping (Facebook page meta, Linktree, local directory snippets)
    Returns (emails_list, discovered_socials, discovered_phone)
    """
    if not biz_name:
        return [], [], ""

    emails = []
    found_socials = list(socials or [])
    found_phone = existing_phone or ""

    queries = [
        f'"{biz_name}" {city} email OR contact',
        f'"{biz_name}" {city} facebook OR instagram OR phone',
    ]

    soc_pattern = re.compile(
        r"https?://(?:www\.)?(?:instagram\.com|facebook\.com|linktr\.ee|wa\.me|twitter\.com|x\.com|tiktok\.com|linkedin\.com)/[a-zA-Z0-9_./-]+",
        re.I,
    )

    candidate_pages = []

    for q in queries:
        try:
            raw_html = search_web_snippets(q, timeout=4)
            if not raw_html:
                continue

            # 1. Extract emails directly from search snippets!
            snippet_emails = extract_emails_from_text(raw_html)
            for e in snippet_emails:
                if e not in emails:
                    emails.append(e)

            # 2. Extract social profiles from search links
            uddg_links = re.findall(r'href=["\'](?:https?:)?//duckduckgo\.com/l/\?uddg=([^"\'&]+)', raw_html)
            decoded_links = [urllib.parse.unquote(u) for u in uddg_links]
            if not decoded_links:
                decoded_links = re.findall(r'https?://[^\s"\'<>]+', raw_html)

            for link in decoded_links:
                if soc_pattern.match(link):
                    clean_s = link.split("?")[0].rstrip("/")
                    if clean_s not in found_socials and "/p/" not in clean_s and "/posts/" not in clean_s:
                        found_socials.append(clean_s)
                if len(candidate_pages) < 2 and any(
                    k in link.lower() for k in ("facebook.com", "linktr.ee", "finelib.", "businesslist.", "vconnect.", "yellowpages", "yelp.com")
                ):
                    candidate_pages.append(link)

            # 3. Extract phone from snippets if business had no phone
            if not found_phone:
                snippet_text = re.sub(r"<[^>]+>", " ", raw_html)
                pm = PHONE_INTL_RE.search(snippet_text)
                if pm:
                    digits = re.sub(r"\D", "", pm.group(0))
                    if 9 <= len(digits) <= 15:
                        found_phone = pm.group(0).strip()

            if emails:
                break
        except Exception:
            continue

    # If still no email, inspect up to 2 discovered public directory/social pages
    if not emails and candidate_pages:
        for page_url in candidate_pages[:2]:
            try:
                req = urllib.request.Request(page_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=3.5, context=SSL_UNVERIFIED) as resp:
                    p_html = resp.read(180000).decode("utf-8", "ignore")
                    p_emails = extract_emails_from_text(p_html)
                    for e in p_emails:
                        if e not in emails:
                            emails.append(e)
                    if emails:
                        break
            except Exception:
                continue

    return emails[:3], found_socials[:5], found_phone


def query_hunter_domain(website_url, api_key):
    """Queries Hunter.io domain-search API if a key is configured."""
    if not website_url or not api_key:
        return []
    try:
        parsed = urllib.parse.urlparse(website_url if "://" in website_url else "https://" + website_url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain or "." not in domain:
            return []
        url = f"https://api.hunter.io/v2/domain-search?domain={urllib.parse.quote(domain)}&api_key={urllib.parse.quote(api_key)}&limit=5"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
            mails = [
                item.get("value", "").lower()
                for item in data.get("data", {}).get("emails", [])
                if item.get("value")
            ]
            return filter_valid_emails(mails)
    except Exception:
        return []


def resolve_dm_channel(socials, phone=""):
    """
    Determines the best 1-click DM link and platform label when reaching out via Social / WhatsApp.
    Returns dict: {platform, handle, dm_url, profile_url}
    """
    socials = socials or []
    for s in socials:
        s_low = s.lower()
        parsed = urllib.parse.urlparse(s if "://" in s else "https://" + s)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        handle = path_parts[-1] if path_parts else ""

        if "instagram.com" in s_low and handle and handle not in ("p", "reel", "explore", "stories"):
            clean_h = handle.lstrip("@")
            return {
                "platform": "Instagram",
                "handle": f"@{clean_h}",
                "dm_url": f"https://ig.me/m/{clean_h}",
                "profile_url": f"https://www.instagram.com/{clean_h}/",
            }
        if "facebook.com" in s_low and handle:
            clean_h = handle.lstrip("@")
            dm_target = f"https://m.me/{clean_h}" if clean_h not in ("profile.php", "pages", "groups") else s
            return {
                "platform": "Facebook",
                "handle": clean_h if clean_h != "profile.php" else "Facebook Page",
                "dm_url": dm_target,
                "profile_url": s,
            }
        if ("twitter.com" in s_low or "x.com" in s_low) and handle:
            clean_h = handle.lstrip("@")
            return {
                "platform": "X",
                "handle": f"@{clean_h}",
                "dm_url": f"https://x.com/{clean_h}",
                "profile_url": f"https://x.com/{clean_h}",
            }
        if "linkedin.com" in s_low:
            return {
                "platform": "LinkedIn",
                "handle": handle or "Company Page",
                "dm_url": s,
                "profile_url": s,
            }
        if "tiktok.com" in s_low and handle:
            clean_h = handle.lstrip("@")
            return {
                "platform": "TikTok",
                "handle": f"@{clean_h}",
                "dm_url": f"https://www.tiktok.com/@{clean_h}",
                "profile_url": f"https://www.tiktok.com/@{clean_h}",
            }
        if "linktr.ee" in s_low:
            return {
                "platform": "Linktree",
                "handle": handle or "Linktree",
                "dm_url": s,
                "profile_url": s,
            }

    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 7:
        return {
            "platform": "WhatsApp",
            "handle": phone,
            "dm_url": f"https://wa.me/{digits}",
            "profile_url": f"https://wa.me/{digits}",
        }

    return {"platform": "", "handle": "", "dm_url": "", "profile_url": ""}


def audit_working_website(html, final_url, note="", elapsed_sec=0.0, category=""):
    """
    Performs an instant technical, SEO, and conversion audit on a working website's HTML.
    Returns (audit_issues_list, primary_service_recommendation)
    """
    issues = []
    h_low = (html or "").lower()

    # 1. Check SSL / Security warning
    if "ssl warning" in (note or "").lower() or (final_url or "").startswith("http://"):
        issues.append("Insecure SSL / HTTP")

    # 2. Check Page Speed
    if elapsed_sec >= 2.8:
        issues.append(f"Slow Load ({elapsed_sec:.1f}s)")

    # 3. Check Mobile Viewport
    if 'name="viewport"' not in h_low and "name='viewport'" not in h_low:
        issues.append("Not Mobile-Friendly")

    # 4. Check Live Chat / AI Receptionist / WhatsApp Widget
    has_chat = any(
        k in h_low
        for k in (
            "wa.me/", "api.whatsapp.com", "tawk.to", "intercom", "crisp.chat",
            "tidio", "drift.com", "livechat", "hubspot", "zendesk", "freshchat", "chat-widget"
        )
    )
    if not has_chat:
        issues.append("No WhatsApp / AI Chat Widget")

    # 5. Check Online Booking / Appointment System
    booking_cats = ("clinic", "dentist", "dental", "doctor", "hospital", "salon", "barber", "spa", "hotel", "resort", "restaurant", "lawyer", "gym", "fitness", "mechanic")
    has_booking = any(
        k in h_low
        for k in (
            "calendly", "acuity", "book-now", "book_now", "appointment", "reservation",
            "opentable", "fresha", "mindbody", "simplybook", "setmore", "booking"
        )
    )
    if not has_booking and any(c in (category or "").lower() for c in booking_cats):
        issues.append("No Online Booking System")

    # 6. Check Local SEO Schema (JSON-LD)
    if "application/ld+json" not in h_low:
        issues.append("Missing Local SEO Schema")

    # 7. Check Meta Description
    if 'name="description"' not in h_low and "name='description'" not in h_low:
        issues.append("Missing Meta Description")

    # 8. Check Retargeting / Analytics Pixels (Meta Pixel / Google Tag)
    has_pixel = any(
        k in h_low
        for k in ("fbq(", "connect.facebook.net", "googletagmanager.com", "gtag(", "google-analytics.com")
    )
    if not has_pixel:
        issues.append("No Ad Retargeting Pixel")

    # 9. Check Outdated Copyright Year
    yr_match = re.search(r"(?:©|&copy;|copyright)\s*(?:20\d\d\s*[-–]\s*)?(20(?:1\d|2[0-3]))\b", h_low)
    if yr_match:
        issues.append(f"Outdated Site ({yr_match.group(1)})")

    if not issues:
        issues.append("Conversion & AI Upgrade Opportunity")

    return issues[:4]


def calculate_lead_score(b):
    """Calculates a 0-100 opportunity score for sorting and prioritization."""
    status = b.get("site_status", "no_website")
    score = 35
    if status == "no_website":
        score = 62
    elif status == "broken":
        score = 66
    elif status == "social_only":
        score = 58
    elif status == "working":
        issues = b.get("audit_issues") or []
        score = 40 + min(len(issues) * 5, 20)

    if b.get("email"):
        score += 6 if b.get("email_guessed") else 18
    if b.get("phone"):
        score += 10
    if b.get("socials"):
        score += 6
    if (b.get("reviews") or 0) >= 10 or (b.get("rating") or 0) >= 4.0:
        score += 6

    return min(99, score)


def generate_outreach(b, settings=None, angle_override=None):
    """
    Generates a high-converting, human-written Email Subject, Email Body, and Short DM/WhatsApp Pitch
    strictly tailored to that specific business, its category problem, city, live audit findings, and pitch angle.
    """
    s = settings or get_settings()
    biz_name = (b.get("name") or "there").strip()
    raw_cat = (b.get("category") or "business").replace("_", " ").strip().lower()
    city = (b.get("city") or "your area").split(",")[0].strip()
    status = b.get("site_status") or "no_website"
    site_note = b.get("site_note") or ""
    website = b.get("website") or ""
    clean_domain = re.sub(r"^https?://(www\.)?", "", website).split("/")[0] if website else ""
    rating = b.get("rating")
    reviews = b.get("reviews")
    audit_issues = b.get("audit_issues") or []
    dm_info = b.get("dm_info") or {}
    platform = dm_info.get("platform") or "social media"

    sender_name = s.get("sender_name") or "Frank Oge"
    sender_company = s.get("sender_company") or "Hackverse Technologies"
    sender_portfolio = s.get("sender_portfolio") or "https://frankoge.com"
    custom_offer = (s.get("custom_offer") or "").strip()
    angle = (angle_override or s.get("pitch_angle") or "auto").strip() or "auto"
    if angle == "custom" and not custom_offer:
        angle = "auto"

    sig_lines = [f"Best regards,\n{sender_name}"]
    if sender_company:
        sig_lines.append(sender_company)
    if sender_portfolio:
        sig_lines.append(sender_portfolio)
    if s.get("sender_phone"):
        sig_lines.append(s["sender_phone"])
    signature = "\n".join(sig_lines)

    rating_line = ""
    if rating and reviews:
        rating_line = f" (and saw your {rating}★ rating across {reviews} reviews — fantastic reputation!)"
    elif rating:
        rating_line = f" (and noticed your {rating}★ rating!)"

    # Identify industry type for deep tailoring
    is_clinic = any(w in raw_cat for w in ("clinic", "dentist", "dental", "doctor", "health", "hospital", "physio", "medical", "care"))
    is_salon = any(w in raw_cat for w in ("salon", "hair", "beauty", "barber", "spa", "cosmetic", "massage", "nails", "aesthetic"))
    is_bakery = any(w in raw_cat for w in ("bakery", "baker", "pastry", "cake", "cafe", "coffee", "restaurant", "bistro", "diner", "food"))
    is_fitness = any(w in raw_cat for w in ("gym", "fitness", "sport", "crossfit", "trainer", "yoga"))
    is_trades = any(w in raw_cat for w in ("plumber", "electrician", "contractor", "mechanic", "car", "auto", "repair"))

    # Custom offer override
    if custom_offer and angle == "custom":
        subject = f"Quick question for {biz_name} in {city}"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"I came across {biz_name} while researching top {raw_cat}s in {city}{rating_line}.\n\n"
            f"{custom_offer}\n\n"
            f"Would you be open to a quick 5-minute chat this week to see if this makes sense for {biz_name}?\n\n"
            f"{signature}"
        )
        dm = (
            f"Hi {biz_name} team! Found you in {city}{rating_line}. "
            f"{custom_offer} — open to a quick chat? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    # =========================================================================
    # CASE 1: NO WEBSITE
    # =========================================================================
    if status == "no_website":
        if angle == "ai_automation":
            subject = f"24/7 AI reception & WhatsApp booking for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I spotted {biz_name} while looking up {raw_cat}s in {city} on Google Maps{rating_line}.\n\n"
                f"I noticed there isn't a website or instant booking channel linked to your listing yet — meaning after-hours inquiries and weekend searchers in {city} often go unanswered until reception opens.\n\n"
                f"I build automated 24/7 AI reception & WhatsApp booking hubs for {raw_cat}s that answer common customer questions, qualify inquiries, and book appointments automatically.\n\n"
                f"Would you be open to seeing a quick interactive demo customized for {biz_name}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name} team! Found your listing in {city} on Maps{rating_line}. "
                f"Noticed there's no website or 24/7 booking link yet for after-hours inquiries. "
                f"I put together a quick AI & WhatsApp booking flow concept for {biz_name} — mind if I share a demo link? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "local_seo":
            subject = f"Ranking {biz_name} higher on Google Maps in {city}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I came across {biz_name} while searching for {raw_cat}s in {city} on Google Maps{rating_line}.\n\n"
                f"Because your listing doesn't currently have a website with LocalBusiness schema linked to it, Google often ranks nearby competitors ahead of you in the Local 3-Pack for '{raw_cat} in {city}'.\n\n"
                f"I specialize in Local SEO + high-speed landing pages that feed Google exact service, location, and trust signals so {biz_name} captures more organic Maps calls.\n\n"
                f"Mind if I send a 2-minute breakdown of how we can boost {biz_name}'s Maps visibility?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name} team! Found you in {city} on Google Maps{rating_line}. "
                f"Without a website & Local SEO schema linked, Google often favors competitors in the Top 3 map results. "
                f"Mind if I share a quick Maps ranking breakdown for {biz_name}? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "ads_funnel":
            subject = f"Turning local {city} searches into booked clients for {biz_name}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I found {biz_name} while researching top {raw_cat}s in {city}{rating_line}.\n\n"
                f"I noticed you don't have a dedicated landing page or retargeting funnel linked to your Maps profile yet — which makes it tough to capture and re-engage local customers searching in {city}.\n\n"
                f"I put together a focused 1-page conversion funnel concept for {biz_name} designed for instant WhatsApp/call leads and low-cost Meta & Google retargeting.\n\n"
                f"Open to taking a quick look at the mockup? No obligation.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name} team! Spotted you in {city}{rating_line}. "
                f"Noticed you don't have a lead-capture funnel linked yet for local searchers. "
                f"I mocked up a clean 1-page offer & retargeting funnel for {biz_name} — can I send the preview? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if is_clinic:
            subject = f"Capturing after-hours patient inquiries for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I was looking up {raw_cat}s in {city} on Google Maps today and came across {biz_name}{rating_line}.\n\n"
                f"I noticed you don't currently have a website linked to your listing. When patients search Google in {city} (especially in the evenings or weekends), they look for a site to view treatments, doctor profiles, and book or ask questions on WhatsApp. Without a site, they usually click the next clinic on Maps.\n\n"
                f"I put together a clean, mobile-fast website layout specifically for {biz_name} — with instant 24/7 WhatsApp triage, patient appointment booking, and Google Maps Local SEO.\n\n"
                f"Mind if I send over a quick preview link for you to see how it looks? Zero obligation.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name}! Found your clinic listing in {city} on Maps{rating_line}. "
                f"Noticed you don't have a website linked yet for patients searching after-hours. "
                f"I mocked up a clean, mobile-fast site layout for {biz_name} with direct WhatsApp appointment booking & Local SEO. "
                f"Mind if I send the preview link? — {sender_name} ({sender_portfolio})"
            )
        elif is_salon:
            subject = f"1-click appointment booking & client capture for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I was looking at top beauty & styling spots in {city} on Google Maps today and found {biz_name}{rating_line}.\n\n"
                f"I noticed there's no website linked to your listing yet. Right now, when local clients in {city} search Maps for a {raw_cat}, they want to see treatment prices, lookbooks, and book appointments directly without playing phone tag.\n\n"
                f"I designed a modern, mobile-first website concept specifically for {biz_name} — complete with a visual service lookbook, automated booking calendar, and 1-click WhatsApp inquiry.\n\n"
                f"Mind if I share a quick preview link so you can take a look? No cost or strings attached.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Found your {raw_cat} listing in {city} on Google Maps{rating_line}. "
                f"Noticed you don't have a website linked yet for new clients looking to see prices & book. "
                f"I sketched out a clean mobile lookbook & booking mockup for {biz_name}. "
                f"Can I drop the preview link for you? — {sender_name} ({sender_portfolio})"
            )
        elif is_bakery:
            subject = f"Mobile visual menu & custom order capture for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I was searching for great bakeries & cafes in {city} on Google Maps and came across {biz_name}{rating_line}.\n\n"
                f"I noticed you don't currently have a website linked to your listing. When customers in {city} search for custom cakes, catering, or daily bakes, they tap listings with a site to view the menu and send quick inquiries on WhatsApp.\n\n"
                f"I put together a clean, fast mobile menu & lookbook concept for {biz_name} that lets local customers view your offerings and order custom bakes directly.\n\n"
                f"Would you be open to checking out a quick preview link? Free to check out.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name} team! Loved finding your {raw_cat} in {city} on Google Maps{rating_line}. "
                f"Noticed you don't have a website linked yet for customers checking menus & custom orders. "
                f"I mocked up a visual mobile lookbook & WhatsApp ordering layout for {biz_name}. "
                f"Mind if I send the preview link? — {sender_name} ({sender_portfolio})"
            )
        elif is_fitness:
            subject = f"Free trial passes & membership signups for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I came across {biz_name} while searching for {raw_cat} spots in {city} on Google Maps{rating_line}.\n\n"
                f"I noticed you don't have a website linked to your listing yet. Local residents searching Google for a {raw_cat} in {city} usually want to check class times, membership rates, and claim a trial pass right away.\n\n"
                f"I put together a clean, mobile-first website & trial-pass capture layout for {biz_name} with instant WhatsApp inquiry.\n\n"
                f"Mind if I share a quick preview link for you to see? Zero obligation.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Found you in {city} on Google Maps{rating_line}. "
                f"Noticed there's no website linked yet for people checking class schedules & trial passes. "
                f"I mocked up a fast trial-pass & WhatsApp signup site for {biz_name} — can I send the preview? — {sender_name} ({sender_portfolio})"
            )
        elif is_trades:
            subject = f"Instant quote requests & click-to-call for {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I found {biz_name} while looking up {raw_cat} services in {city} on Google Maps{rating_line}.\n\n"
                f"I noticed you don't currently have a website linked to your listing. When local homeowners or drivers in {city} have an urgent job, they check listings with a clean site showing services, service areas, and 1-tap WhatsApp or call buttons.\n\n"
                f"I drafted a fast, no-nonsense website mockup for {biz_name} built to capture emergency calls and instant quote requests.\n\n"
                f"Would you like me to send over the preview link?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name} team! Spotted your {raw_cat} listing in {city} on Maps{rating_line}. "
                f"Noticed you don't have a website linked yet for quick quote requests & emergency calls. "
                f"I mocked up a clean, mobile-ready site for {biz_name} — mind if I send the link? — {sender_name} ({sender_portfolio})"
            )
        else:
            subject = f"Quick question about {biz_name} ({city})"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I was looking up {raw_cat}s in {city} on Google Maps today and came across {biz_name}{rating_line}.\n\n"
                f"I noticed you don't currently have a website linked to your listing. Right now, when local customers in {city} search Google for a {raw_cat}, they check listings with a site where they can view services, check prices, or message directly on WhatsApp.\n\n"
                f"I went ahead and mapped out a clean, mobile-fast website layout specifically for {biz_name} — complete with instant WhatsApp inquiry, Google Maps SEO, and online booking/lead capture.\n\n"
                f"Mind if I send over a quick preview link so you can see how it looks? No cost or obligation at all.\n\n"
                f"{signature}"
            )
            dm = (
                f"Hi {biz_name}! I found your {raw_cat} listing in {city} on Google Maps{rating_line}, "
                f"and noticed there's no website linked yet for customers trying to check you out online. "
                f"I put together a clean, mobile-friendly website mockup specifically for {biz_name} with direct WhatsApp inquiry & Local SEO. "
                f"Mind if I send you the preview link to check out? — {sender_name} ({sender_portfolio})"
            )
        return {"subject": subject, "body": body, "dm": dm}

    # =========================================================================
    # CASE 2: SOCIAL ONLY (Instagram / Facebook / Linktree)
    # =========================================================================
    if status == "social_only":
        if angle == "ai_automation":
            subject = f"Automating {biz_name}'s {platform} DMs & WhatsApp bookings"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I checked out {biz_name}'s {platform} page in {city}{rating_line} — great presence!\n\n"
                f"Since your web link points to {platform}, I'm guessing a lot of client questions, pricing checks, and booking requests pile up manually in DMs — especially after hours.\n\n"
                f"I set up 24/7 AI reception & WhatsApp booking workflows that plug right into your {platform} bio so customers get instant answers and confirmed slots automatically.\n\n"
                f"Open to seeing a 1-minute demo tailored for {biz_name}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Love your {platform} page. Since you're sending traffic here, I thought you might appreciate an automated WhatsApp/DM booking flow that answers FAQs & books clients 24/7. "
                f"Mind if I share a quick demo? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "local_seo":
            subject = f"Capturing Google Maps traffic alongside {biz_name}'s {platform}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I spotted {biz_name} in {city} and checked out your {platform} page{rating_line}.\n\n"
                f"Relying solely on {platform} works well for followers, but Google rarely ranks social profiles in the Local 3-Pack for '{raw_cat} in {city}' — meaning high-intent Google searchers often miss you.\n\n"
                f"I build fast, Local-SEO-optimized microsites with Google Schema that complement your {platform} and push {biz_name} up the local search rankings.\n\n"
                f"Can I send over a quick preview showing how this pairs with your {platform}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Great {platform} page. Just noticed Google Maps usually ranks dedicated local sites above social links for '{raw_cat} in {city}'. "
                f"I sketched a Local-SEO landing page that pairs with your {platform} — mind if I share it? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "ads_funnel":
            subject = f"Turning {biz_name}'s {platform} visitors into tracked bookings"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"Loved seeing {biz_name}'s {platform} presence in {city}{rating_line}.\n\n"
                f"Right now, without a dedicated landing page carrying a Meta/Google retargeting pixel, anyone who checks your {platform} or Maps listing and gets distracted is hard to follow up with.\n\n"
                f"I build fast bio-link conversion funnels with built-in retargeting pixels and 1-tap booking so your {platform} and Google traffic converts consistently.\n\n"
                f"Mind if I share a quick visual mockup for {biz_name}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Love your {platform}. Noticed you don't have a pixel-tracked booking funnel behind your bio link yet to re-engage visitors. "
                f"I mocked up a quick funnel concept for {biz_name} — can I send it over? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if is_salon:
            subject = f"Cutting out DM phone-tag for {biz_name} in {city}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I just checked out {biz_name} in {city} and saw your {platform} page{rating_line} — your work looks amazing!\n\n"
                f"I noticed you're currently relying solely on {platform} DMs for client bookings. The challenge with DMs is that customers often message late, back-and-forth scheduling causes friction, and you miss high-intent Google searchers in {city} who don't browse social media.\n\n"
                f"I build sleek, fast booking websites that link directly to your {platform} bio and Google Maps profile, letting clients reserve appointments & pay deposits 24/7 automatically.\n\n"
                f"Would you be open to seeing a quick 1-page preview I mocked up for {biz_name}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Love your {platform} page. Noticed you're handling bookings through DMs. "
                f"I put together a fast 1-page booking concept for {biz_name} that lets clients book instantly from your bio & Google Maps without the DM back-and-forth. "
                f"Mind if I drop the preview link? — {sender_name} ({sender_portfolio})"
            )
        else:
            subject = f"{biz_name}'s {platform} page + capturing Google search clients in {city}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"I just checked out {biz_name} in {city} and saw your {platform} page{rating_line} — great brand presence!\n\n"
                f"I noticed you're currently directing people to {platform} instead of a dedicated website. While social media is great for branding, customers searching Google Maps for a {raw_cat} in {city} have immediate buying intent, and DMs often create friction compared to a 1-click booking or inquiry page.\n\n"
                f"I build fast, high-converting websites for {raw_cat}s that sync with your {platform}, rank on Google Maps in {city}, and turn visitors into confirmed bookings/WhatsApp leads automatically.\n\n"
                f"Would you be open to seeing a quick 1-page mockup I sketched out for {biz_name}?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Love your {platform} page. I noticed when searching for {raw_cat}s in {city} on Google Maps that you don't have a dedicated website linked yet. "
                f"I mocked up a clean, fast website concept for {biz_name} that turns your {platform} & Google visitors into instant bookings/clients. "
                f"Can I drop the preview link here for you to see? — {sender_name} ({sender_portfolio})"
            )
        return {"subject": subject, "body": body, "dm": dm}

    # =========================================================================
    # CASE 3: BROKEN WEBSITE
    # =========================================================================
    if status == "broken":
        err_desc = site_note.lower() if site_note else "not loading properly"
        if angle == "ai_automation":
            subject = f"{biz_name}'s website link is down — quick fix + 24/7 WhatsApp capture"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"Quick heads-up — I clicked through to {biz_name}'s website ({clean_domain or website}) in {city}{rating_line}, and it's currently returning an error ({site_note or err_desc}).\n\n"
                f"Right now, anyone trying to reach you from Google Maps hits a dead link instead of booking or messaging you.\n\n"
                f"I can help get the link back online fast and plug in an instant 24/7 WhatsApp & AI booking widget so you never lose another after-hours inquiry.\n\n"
                f"Want me to send over details on the error and a working preview?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Quick heads-up: {clean_domain or 'your website link'} is currently down ({site_note or 'not loading'}). "
                f"I can help fix it fast and set up a 24/7 WhatsApp/AI inquiry flow so Maps visitors convert instead of bouncing. Mind if I share details? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "local_seo":
            subject = f"Broken site alert ({clean_domain or biz_name}) hurting Google Maps rank in {city}"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"Quick heads-up — I noticed {biz_name}'s linked website ({clean_domain or website}) in {city}{rating_line} is currently throwing an error ({site_note or err_desc}).\n\n"
                f"Beyond frustrating customers clicking from Maps, dead or parked links actively hurt your Local SEO and push your listing down in Google search results for '{raw_cat} in {city}'.\n\n"
                f"I can help diagnose and restore your site (or launch a fast, LocalBusiness-schema-ready replacement) within 24 hours.\n\n"
                f"Want me to send over what's causing the error?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Heads-up: your site ({clean_domain or 'on Maps'}) is throwing an error ({site_note or 'not loading'}), which hurts Google Maps Local SEO in {city}. "
                f"Mind if I send details on what's causing it and how to fix it fast? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        if angle == "ads_funnel":
            subject = f"Heads up: {biz_name}'s site link is down (wasting Maps traffic)"
            body = (
                f"Hi {biz_name} team,\n\n"
                f"Quick heads-up — while looking up {biz_name} in {city}{rating_line}, I tried opening {clean_domain or website} and hit an error ({site_note or err_desc}).\n\n"
                f"Any high-intent customer clicking your Google Maps button or ads right now lands on a dead page instead of a conversion funnel.\n\n"
                f"I already mocked up a fast, pixel-ready replacement landing funnel for {biz_name} (or I can troubleshoot your current domain right away).\n\n"
                f"Would you like me to send the preview link and error details?\n\n"
                f"{signature}"
            )
            dm = (
                f"Hey {biz_name} team! Heads-up: {clean_domain or 'your website link'} is currently down ({site_note or 'not loading'}), so Maps clicks are hitting a dead end. "
                f"I mocked up a clean conversion-funnel replacement (or can help fix the domain) — want to see it? — {sender_name} ({sender_portfolio})"
            )
            return {"subject": subject, "body": body, "dm": dm}

        subject = f"Heads up: {biz_name}'s website link ({clean_domain or 'on Google Maps'}) is down"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"Quick helpful heads-up — I was looking at {biz_name}'s listing in {city}{rating_line} and tried clicking through to your website ({clean_domain or website}), but it's currently returning an error ({site_note or err_desc}).\n\n"
            f"Anyone clicking your website button from Google Maps right now hits a dead end, which usually sends them straight to a competitor in {city}.\n\n"
            f"I'm a web engineer and already put together a modern, fast-loading replacement preview for {biz_name} (or I can help you fix the current domain issue in under 24 hours).\n\n"
            f"Want me to send over the preview link or details on what's causing the error?\n\n"
            f"{signature}"
        )
        dm = (
            f"Hey {biz_name} team! Quick heads-up: I clicked your website link ({clean_domain or 'on your Google Maps listing'}) in {city} and noticed it's currently down ({site_note or 'not loading'}). "
            f"I'm a web developer and mocked up a clean, modern replacement for {biz_name} (or can help fix your domain fast) so you don't lose customers clicking from Maps. "
            f"Mind if I share the preview link? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    # =========================================================================
    # CASE 4: WORKING WEBSITE (CONVERSION AUDIT UPGRADES)
    # =========================================================================
    site_ref = clean_domain or f"{biz_name}'s website"

    if angle == "ai_automation":
        has_chat_gap = any("Chat" in iss or "Booking" in iss for iss in audit_issues)
        gap_note = (
            "I noticed there isn't an instant WhatsApp / AI chat or 1-click booking flow active on the page right now"
            if has_chat_gap
            else "adding a faster 24/7 AI reception & WhatsApp booking flow could capture significantly more after-hours visitors"
        )
        subject = f"Adding 24/7 AI & WhatsApp booking to {site_ref}"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"I was checking out {site_ref} after finding {biz_name} in {city}{rating_line}.\n\n"
            f"Your site gives a great overview, though {gap_note}. Mobile visitors searching in the evenings often bounce if they can't get an instant answer or book without calling.\n\n"
            f"I put together a quick interactive preview showing how a 24/7 AI receptionist + WhatsApp booking widget would fit right onto {site_ref}.\n\n"
            f"Mind if I send that preview over for you to test?\n\n"
            f"{signature}"
        )
        dm = (
            f"Hi {biz_name} team! Checked out {site_ref} in {city}{rating_line}. "
            f"I mocked up a quick 24/7 AI & WhatsApp booking widget tailored for {site_ref} to capture after-hours visitors without phone tag — mind if I send the preview? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    if angle == "local_seo":
        seo_gaps = [i for i in audit_issues if any(k in i for k in ("Schema", "Meta", "Slow Load", "SSL", "Mobile"))]
        gap_summary = " and ".join(seo_gaps[:2]) if seo_gaps else "missing LocalBusiness schema & on-page search signals"
        subject = f"Boosting {site_ref} into the {city} Google Maps Top 3"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"I came across {biz_name} in {city}{rating_line} and took a quick look at {site_ref}.\n\n"
            f"While auditing the site, I spotted a couple of technical SEO gaps ({gap_summary}) that typically hold local businesses back from ranking in the Google Maps Top-3 Pack for '{raw_cat} in {city}'.\n\n"
            f"I put together a quick 1-page SEO checklist specifically for {site_ref} showing what to fix first.\n\n"
            f"Mind if I send it over? Zero obligation.\n\n"
            f"{signature}"
        )
        dm = (
            f"Hi {biz_name} team! Checked out {site_ref} in {city}{rating_line}. "
            f"Spotted a couple of Local SEO fixes ({gap_summary}) that could move {biz_name} higher on Google Maps. Mind if I share the quick checklist? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    if angle == "ads_funnel":
        has_pixel_gap = any("Pixel" in iss for iss in audit_issues)
        pixel_line = (
            f"I noticed {site_ref} doesn't currently have a Meta or Google retargeting pixel firing"
            if has_pixel_gap
            else f"pairing {site_ref} with a focused retargeting & lead-capture funnel"
        )
        subject = f"Recovering lost website visitors on {site_ref}"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"I was checking out {site_ref} after finding {biz_name} in {city}{rating_line}.\n\n"
            f"Over 90% of local visitors leave a site without calling or booking on their first visit — and {pixel_line}, so those potential clients in {city} aren't being re-engaged.\n\n"
            f"I mapped out a simple conversion + retargeting funnel concept for {site_ref} to turn existing traffic into predictable weekly bookings.\n\n"
            f"Would you like me to send over the brief breakdown?\n\n"
            f"{signature}"
        )
        dm = (
            f"Hi {biz_name} team! Checked out {site_ref} in {city}{rating_line}. "
            f"Spotted an easy win to capture & retarget the 90% of visitors who browse without booking right away. Mind if I send a quick breakdown? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    if angle in ("web_design", "redesign"):
        design_gaps = [i for i in audit_issues if any(k in i for k in ("Mobile", "Slow Load", "SSL", "Outdated", "Booking", "Chat"))]
        gap_text = ", ".join(design_gaps[:2]) if design_gaps else "mobile speed and modern conversion layout"
        subject = f"Modern redesign concept for {site_ref}"
        body = (
            f"Hi {biz_name} team,\n\n"
            f"I found {biz_name} in {city}{rating_line} and had a look at {site_ref}.\n\n"
            f"Your business has a strong local reputation, though {site_ref} could convert noticeably more mobile visitors by tightening up {gap_text}.\n\n"
            f"I put together a clean, modern redesign concept specifically for {biz_name} so your website reflects the same quality clients experience in person.\n\n"
            f"Mind if I send over the preview link?\n\n"
            f"{signature}"
        )
        dm = (
            f"Hi {biz_name} team! Looked at {site_ref} in {city}{rating_line}. "
            f"Put together a modern, mobile-fast redesign concept addressing {gap_text} — mind if I share the preview link? — {sender_name} ({sender_portfolio})"
        )
        return {"subject": subject, "body": body, "dm": dm}

    issue_explanations = {
        "No WhatsApp / AI Chat Widget": f"Adding a 24/7 instant WhatsApp / AI inquiry widget so mobile visitors asking questions after-hours get answered immediately instead of bouncing",
        "No Online Booking System": f"Adding a 1-click online booking/appointment calendar so clients in {city} can book without having to call reception first",
        "Missing Local SEO Schema": f"Adding LocalBusiness Google Schema markup so {biz_name} ranks higher in the Google Maps Top-3 pack for '{raw_cat} in {city}'",
        "Missing Meta Description": f"Fixing missing SEO meta descriptions that are currently hurting your Google search click-through rate",
        "No Ad Retargeting Pixel": f"Installing Meta/Google retargeting tracking so you can re-engage the 90%+ of visitors who check your site and leave without booking",
        "Insecure SSL / HTTP": f"Resolving the SSL security certificate warning so browsers stop warning visitors that {clean_domain or 'your site'} is 'Not Secure'",
        "Not Mobile-Friendly": f"Upgrading mobile responsiveness so smartphone users in {city} can navigate and book effortlessly",
    }

    bullets = []
    for iss in audit_issues:
        if iss in issue_explanations:
            bullets.append(f"• {issue_explanations[iss]}")
        elif iss.startswith("Slow Load"):
            bullets.append(f"• Speeding up your mobile load time ({iss}) so visitors don't bounce before your page renders")
        elif iss.startswith("Outdated Site"):
            bullets.append(f"• Refreshing the visual layout & trust signals ({iss}) to match your 5-star offline reputation")

    if not bullets:
        if is_clinic:
            bullets = [
                f"• Adding an instant 24/7 WhatsApp patient triage widget for after-hours appointments",
                f"• Implementing LocalBusiness medical schema so {biz_name} dominates Google Maps searches in {city}",
            ]
        elif is_salon:
            bullets = [
                f"• Adding a 1-click booking flow so clients reserve appointments without DM phone-tag",
                f"• Optimizing Local SEO schema so you rank #1 for '{raw_cat} in {city}'",
            ]
        elif is_bakery:
            bullets = [
                f"• Adding a mobile visual lookbook with 1-click WhatsApp custom cake/catering ordering",
                f"• Boosting Local SEO schema to capture top placement on Google Maps in {city}",
            ]
        else:
            bullets = [
                f"• Adding an instant WhatsApp & AI lead-capture widget to convert more of your current traffic into booked clients",
                f"• Optimizing your Local SEO schema so {biz_name} ranks higher on Google Maps for '{raw_cat} in {city}'",
            ]

    bullet_block = "\n".join(bullets[:2])

    subject = f"2 quick conversion wins I spotted on {site_ref}"
    body = (
        f"Hi {biz_name} team,\n\n"
        f"I was checking out {site_ref} after finding {biz_name} in {city}{rating_line}. You have a great foundation, but while inspecting the site I noticed two quick upgrades that would noticeably increase customer inquiries and bookings:\n\n"
        f"{bullet_block}\n\n"
        f"I prepared a quick visual mockup showing exactly how this would look on {site_ref} and how quickly we can plug it in.\n\n"
        f"Mind if I send that over for you to take a look? Zero pressure or obligation.\n\n"
        f"{signature}"
    )
    first_issue = audit_issues[0] if audit_issues else "conversion & Local SEO upgrades"
    dm = (
        f"Hi {biz_name} team! Just checked out {site_ref} in {city}{rating_line}. "
        f"Great site, though I spotted a couple of quick wins ({first_issue}) that could bring in noticeably more client inquiries/bookings from Google. "
        f"I put together a quick preview showing the fix — mind if I send it over? — {sender_name} ({sender_portfolio})"
    )
    return {"subject": subject, "body": body, "dm": dm}


def generate_ai_outreach(b, settings=None, angle_override=None):
    """
    If Gemini or Groq API key is configured, uses LLM to craft a hyper-personalized outreach pitch,
    falling back seamlessly to the deterministic engine if no key is configured or on error.
    """
    s = settings or get_settings()
    base = generate_outreach(b, s, angle_override)
    gemini_key = (s.get("gemini_api_key") or "").strip()
    groq_key = (s.get("groq_api_key") or "").strip()

    if not gemini_key and not groq_key:
        return base

    prompt = (
        f"You are {s.get('sender_name', 'Frank Oge')} from {s.get('sender_company', 'Hackverse Technologies')} ({s.get('sender_portfolio', 'https://frankoge.com')}).\n"
        f"Write a short, natural, human-convincing cold outreach email and a short DM for this local business lead:\n"
        f"- Business Name: {b.get('name')}\n"
        f"- Category: {b.get('category')}\n"
        f"- City: {b.get('city')}\n"
        f"- Website Status: {b.get('site_status')} ({b.get('site_note')})\n"
        f"- Website URL: {b.get('website') or 'None'}\n"
        f"- Audit Findings: {', '.join(b.get('audit_issues') or []) or 'None'}\n"
        f"- Rating: {b.get('rating') or 'N/A'} ({b.get('reviews') or 0} reviews)\n"
        f"- Desired Pitch Angle: {angle_override or s.get('pitch_angle', 'auto')}\n\n"
        "Return strictly valid JSON with keys: \"subject\", \"body\", \"dm\". Keep the email under 130 words, warm, specific, zero fluff, ending with a low-friction question and signed with the sender's name, company, and portfolio URL."
    )

    try:
        if gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={urllib.parse.quote(gemini_key)}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6},
            }
            req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                resp = json.load(r)
                txt = resp["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(txt)
                if parsed.get("subject") and parsed.get("body"):
                    return {
                        "subject": parsed["subject"],
                        "body": parsed["body"],
                        "dm": parsed.get("dm") or base["dm"],
                    }
    except Exception:
        pass

    try:
        if groq_key:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.6,
            }
            req = urllib.request.Request(
                url,
                json.dumps(payload).encode(),
                {"Content-Type": "application/json", "Authorization": f"Bearer {groq_key}"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                resp = json.load(r)
                txt = resp["choices"][0]["message"]["content"]
                parsed = json.loads(txt)
                if parsed.get("subject") and parsed.get("body"):
                    return {
                        "subject": parsed["subject"],
                        "body": parsed["body"],
                        "dm": parsed.get("dm") or base["dm"],
                    }
    except Exception:
        pass

    return base


def send_smtp_email(to_email, subject, body, biz_name="", force=False):
    """
    Sends an email via configured SMTP.
    Enforces atomic single-send deduplication across threads unless force=True (manual user click).
    Returns dict: {ok, status, message}
    """
    s = get_settings()
    to_clean = (to_email or "").split(",")[0].strip().lower()
    if not to_clean or "@" not in to_clean:
        return {"ok": False, "status": "no_email", "message": "No valid recipient email."}

    if s.get("dry_run"):
        with _LOCK:
            if not force and (to_clean in _INFLIGHT_EMAILS or to_clean in _read_sent_ledger_unlocked()):
                return {"ok": True, "status": "already_sent", "message": f"Already emailed {to_clean} previously (skipped)."}
            ledger = _read_sent_ledger_unlocked()
            ledger[to_clean] = {
                "biz_name": biz_name,
                "subject": subject,
                "sent_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            _atomic_write_json(SENT_LOG_FILE, ledger)
        return {"ok": True, "status": "simulated", "message": f"Dry-run simulated send to {to_clean}"}

    smtp_user = (s.get("smtp_email") or "").strip()
    smtp_pass = (s.get("smtp_password") or "").strip()
    smtp_host = (s.get("smtp_host") or "smtp.gmail.com").strip()
    smtp_port = int(s.get("smtp_port") or 465)
    sender_name = (s.get("sender_name") or "Frank Oge").strip()

    if not smtp_user or not smtp_pass:
        return {
            "ok": False,
            "status": "unconfigured",
            "message": "SMTP email/password not configured. Open Outreach Settings to add your Gmail App Password or use 'Mail App'.",
        }

    reserved = False
    with _LOCK:
        if not force and (to_clean in _INFLIGHT_EMAILS or to_clean in _read_sent_ledger_unlocked()):
            return {"ok": True, "status": "already_sent", "message": f"Already emailed {to_clean} previously (skipped)."}
        if to_clean not in _INFLIGHT_EMAILS:
            _INFLIGHT_EMAILS.add(to_clean)
            reserved = True

    msg = EmailMessage()
    msg["From"] = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user
    msg["To"] = to_clean
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12, context=ctx) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

        mark_email_sent(to_clean, biz_name, subject)
        return {"ok": True, "status": "sent", "message": f"Sent to {to_clean}"}
    except Exception as e:
        return {"ok": False, "status": "error", "message": f"SMTP error: {str(e)[:120]}"}
    finally:
        if reserved:
            with _LOCK:
                _INFLIGHT_EMAILS.discard(to_clean)
