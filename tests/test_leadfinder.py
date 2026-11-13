import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import outreach
import providers
import server


class IsolatedDataMixin:
    def setUp(self):
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._orig_paths = (
            outreach.DATA_DIR,
            outreach.SETTINGS_FILE,
            outreach.SENT_LOG_FILE,
            outreach.ENV_FILE,
            providers.DATA_DIR,
            providers.GEOCACHE_FILE,
        )
        outreach.DATA_DIR = tmp
        outreach.SETTINGS_FILE = tmp / "settings.json"
        outreach.SENT_LOG_FILE = tmp / "sent_emails.json"
        outreach.ENV_FILE = tmp / ".env"
        providers.DATA_DIR = tmp
        providers.GEOCACHE_FILE = tmp / "geocache.json"
        with outreach._LOCK:
            outreach._INFLIGHT_EMAILS.clear()

    def tearDown(self):
        (
            outreach.DATA_DIR,
            outreach.SETTINGS_FILE,
            outreach.SENT_LOG_FILE,
            outreach.ENV_FILE,
            providers.DATA_DIR,
            providers.GEOCACHE_FILE,
        ) = self._orig_paths
        self._tmpdir.cleanup()
        super().tearDown()


class TestEmailExtractionAndScoring(IsolatedDataMixin, unittest.TestCase):
    def test_extract_emails_from_text_handles_obfuscated_schema_and_junk(self):
        html = """
        <html>
          <script type="application/ld+json">
            {"@type": "LocalBusiness", "email": "mailto:booking@brightclinic.co.uk"}
          </script>
          <body>
            <a href="mailto:hello@brightclinic.co.uk">Email</a>
            <div data-email="care@brightclinic.co.uk"></div>
            <p>Reach us at support [at] brightclinic [dot] com</p>
            <img src="hero@2x.png">
            <a href="https://duckduckgo.com/?q=%22%40gmail.com%22">Search</a>
            <span>noreply@brightclinic.co.uk</span>
          </body>
        </html>
        """
        found = outreach.extract_emails_from_text(html)
        self.assertIn("booking@brightclinic.co.uk", found)
        self.assertIn("hello@brightclinic.co.uk", found)
        self.assertIn("care@brightclinic.co.uk", found)
        self.assertIn("support@brightclinic.com", found)
        self.assertNotIn("hero@2x.png", found)
        self.assertNotIn("noreply@brightclinic.co.uk", found)

    def test_decode_cf(self):
        # Encoded "hello@test.com" with XOR key 0x2a
        key = 0x2A
        plain = "hello@test.com"
        encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in plain)
        self.assertEqual(server.decode_cf(encoded), plain)

    def test_derive_domain_emails_and_exclusions(self):
        bakery_mails = outreach.derive_domain_emails("https://www.sweetcrumb.co.uk", category="bakery")
        self.assertEqual(bakery_mails[0], "enquiries@sweetcrumb.co.uk")
        self.assertIn("orders@sweetcrumb.co.uk", bakery_mails)

        self.assertEqual(outreach.derive_domain_emails("https://myshop.wixsite.com/site", category="salon"), [])
        self.assertEqual(outreach.derive_domain_emails("https://facebook.com/mybiz", category="salon"), [])

    def test_lead_score_distinguishes_verified_and_guessed_email(self):
        base = {"site_status": "working", "audit_issues": ["Slow Load (3.5s)", "Missing Meta Description"]}
        guessed = {**base, "email": "info@example.org", "email_guessed": True}
        verified = {**base, "email": "owner@example.org", "email_guessed": False}
        self.assertGreater(outreach.calculate_lead_score(verified), outreach.calculate_lead_score(guessed))


class TestWebsiteAuditAndPitching(IsolatedDataMixin, unittest.TestCase):
    def test_audit_working_website_flags_gaps(self):
        html = "<html><head><title>Test</title></head><body><footer>© 2021 Acme</footer></body></html>"
        issues = outreach.audit_working_website(
            html, "http://acme.test", note="Loads fine (SSL warning)", elapsed_sec=3.2, category="clinic"
        )
        self.assertIn("Insecure SSL / HTTP", issues)
        self.assertIn("Slow Load (3.2s)", issues)
        self.assertIn("Not Mobile-Friendly", issues)
        self.assertIn("No WhatsApp / AI Chat Widget", issues)
        self.assertEqual(len(issues), 4)

    def test_generate_outreach_honors_all_angles_across_all_statuses(self):
        statuses = ["no_website", "social_only", "broken", "working"]
        angles = ["auto", "web_design", "ai_automation", "local_seo", "ads_funnel", "custom"]
        settings = outreach.get_settings()

        for status in statuses:
            lead = {
                "name": "Apex Dental",
                "category": "dentist",
                "city": "Austin, TX",
                "site_status": status,
                "site_note": "DNS lookup failed" if status == "broken" else "",
                "website": "https://apexdental.test" if status in ("broken", "working") else "",
                "audit_issues": ["No WhatsApp / AI Chat Widget", "Missing Local SEO Schema"] if status == "working" else [],
                "dm_info": {"platform": "Instagram"},
                "rating": 4.9,
                "reviews": 42,
            }
            for angle in angles:
                pitch = outreach.generate_outreach(lead, settings=settings, angle_override=angle)
                self.assertTrue(pitch["subject"], f"Missing subject for {status}/{angle}")
                self.assertTrue(pitch["body"], f"Missing body for {status}/{angle}")
                self.assertTrue(pitch["dm"], f"Missing dm for {status}/{angle}")
                if status in ("no_website", "social_only", "broken"):
                    self.assertNotIn(
                        "2 quick conversion wins I spotted",
                        pitch["subject"],
                        f"Unexpected working-site fallback for {status}/{angle}",
                    )

        custom_settings = {**settings, "custom_offer": "We build 7-day patient intake portals."}
        custom_pitch = outreach.generate_outreach(
            {"name": "Apex Dental", "category": "dentist", "city": "Austin", "site_status": "no_website"},
            settings=custom_settings,
            angle_override="custom",
        )
        self.assertIn("7-day patient intake portals", custom_pitch["body"])


class TestSettingsAndSmtpDeduplication(IsolatedDataMixin, unittest.TestCase):
    def test_settings_preserve_secrets_and_env_precedence(self):
        outreach.ENV_FILE.write_text('GEMINI_API_KEY="env-gemini-key"\nSMTP_HOST="smtp.custom.test"\n', encoding="utf-8")

        # Partial toggle should not freeze .env keys into settings.json
        saved = outreach.save_settings({"auto_send_email": True, "smtp_email": "me@test.com", "smtp_password": "secret-app-password"})
        self.assertTrue(saved["auto_send_email"])
        self.assertEqual(saved["gemini_api_key"], "env-gemini-key")

        # Blank secret fields in subsequent form save should NOT erase existing secret
        saved2 = outreach.save_settings({"sender_name": "Jane Doe", "smtp_password": ""})
        self.assertEqual(saved2["sender_name"], "Jane Doe")
        self.assertEqual(saved2["smtp_password"], "secret-app-password")

        # Public settings redacts secrets but reports configured flags
        pub = outreach.get_public_settings(saved2)
        self.assertEqual(pub["smtp_password"], "")
        self.assertEqual(pub["gemini_api_key"], "")
        self.assertTrue(pub["configured_secrets"]["smtp_password"])
        self.assertTrue(pub["configured_secrets"]["gemini_api_key"])
        self.assertFalse(pub["configured_secrets"]["groq_api_key"])

        # Explicit clear removes secret
        saved3 = outreach.save_settings({"clear_smtp_password": True})
        self.assertEqual(saved3["smtp_password"], "")

    def test_concurrent_smtp_deduplication_sends_only_once(self):
        outreach.save_settings({
            "smtp_email": "sender@agency.test",
            "smtp_password": "app-password",
            "smtp_host": "smtp.agency.test",
            "smtp_port": 465,
            "dry_run": False,
        })

        send_calls = 0
        call_lock = threading.Lock()

        class DummySMTP:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def login(self, user, pw):
                pass
            def send_message(self, msg):
                nonlocal send_calls
                time.sleep(0.03)
                with call_lock:
                    send_calls += 1

        with mock.patch("smtplib.SMTP_SSL", DummySMTP):
            with ThreadPoolExecutor(max_workers=8) as pool:
                futs = [
                    pool.submit(
                        outreach.send_smtp_email,
                        "shared@bakery.test",
                        "Hello",
                        "Body",
                        "Bakery",
                        False,
                    )
                    for _ in range(8)
                ]
                results = [f.result() for f in futs]

        sent = [r for r in results if r["status"] == "sent"]
        skipped = [r for r in results if r["status"] == "already_sent"]
        self.assertEqual(send_calls, 1)
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(skipped), 7)


class TestProviders(IsolatedDataMixin, unittest.TestCase):
    def test_sanitize_http_url_and_escape_overpass_regex(self):
        self.assertEqual(providers.sanitize_http_url("javascript:alert(1)"), "")
        self.assertEqual(providers.sanitize_http_url("data:text/html,hi"), "")
        self.assertEqual(providers.sanitize_http_url("www.example.com/menu"), "https://www.example.com/menu")
        self.assertEqual(providers.sanitize_http_url("http://example.com:8080"), "http://example.com:8080")

        escaped = providers.escape_overpass_regex('Cafe "N" + (Bar)')
        self.assertNotIn('""', escaped)
        self.assertIn(r'\"', escaped)
        self.assertIn(r'\+', escaped)
        self.assertIn(r'\(', escaped)

    def test_parse_osm_element_sanitizes_urls_and_x_handle(self):
        elem = {
            "type": "node",
            "id": 123,
            "lat": 51.5,
            "lon": -0.1,
            "tags": {
                "name": "Corner Bakery",
                "shop": "bakery",
                "website": "javascript:alert(1)",
                "contact:x": "@cornerbakery",
                "contact:whatsapp": "+44 7700 900123",
                "youtube": "javascript:evil()",
            },
        }
        parsed = providers.parse_osm_element(elem, "London")
        self.assertEqual(parsed["website"], "")
        self.assertIn("https://twitter.com/cornerbakery", parsed["socials"])
        self.assertIn("https://wa.me/447700900123", parsed["socials"])
        self.assertFalse(any("javascript:" in s for s in parsed["socials"]))

    def test_parse_photon_results_filters_non_commercial_and_distant_hits(self):
        features = [
            {
                "properties": {"name": "Trail Post", "osm_key": "highway", "osm_value": "footway", "osm_id": 1},
                "geometry": {"coordinates": [-0.1, 51.5]},
            },
            {
                "properties": {"name": "Far Cafe", "osm_key": "amenity", "osm_value": "cafe", "osm_id": 2},
                "geometry": {"coordinates": [5.0, 51.5]},
            },
            {
                "properties": {"name": "Near Cafe", "osm_key": "amenity", "osm_value": "cafe", "osm_id": 3, "city": "London"},
                "geometry": {"coordinates": [-0.11, 51.51]},
            },
        ]
        res = providers.parse_photon_results(features, "cafe", "London", center_lat=51.5, center_lon=-0.1)
        self.assertEqual([r["name"] for r in res], ["Near Cafe"])

    def test_geocode_direct_coordinates(self):
        lat, lon, s, n, w, e, title = providers.geocode("53.3811, -1.4701")
        self.assertAlmostEqual(lat, 53.3811)
        self.assertAlmostEqual(lon, -1.4701)
        self.assertLess(s, n)
        self.assertLess(w, e)
        self.assertEqual(title, "53.3811, -1.4701")


class TestCheckSiteAndEnrich(IsolatedDataMixin, unittest.TestCase):
    def test_empty_200_response_is_broken(self):
        with mock.patch("server.fetch_page", return_value=("<html></html>", "https://empty.test", "Loads fine", True, 200, 0.2)):
            status, note, *_ = server.check_site("https://empty.test", biz_name="Empty Biz", city="Austin")
        self.assertEqual(status, "broken")
        self.assertEqual(note, "Empty page response")

    def test_protected_403_response_is_working_with_manual_review_note(self):
        with (
            mock.patch("server.fetch_page", return_value=("", "https://waf.test", "HTTP 403 (Protected / Active)", True, 403, 0.3)),
            mock.patch("outreach.hunt_site_search_emails", return_value=[]),
            mock.patch("outreach.hunt_emails_without_website", return_value=([], [], "")),
        ):
            status, note, socials, email_str, verified_url, audit_issues, phone, guessed = server.check_site(
                "https://waf.test", biz_name="WAF Clinic", city="Austin", category="clinic"
            )
        self.assertEqual(status, "working")
        self.assertEqual(audit_issues, ["Site Protected (HTTP 403 — Manual Review)"])
        self.assertTrue(guessed)
        self.assertIn("info@waf.test", email_str)

    def test_enrich_skips_auto_send_for_guessed_email_and_sends_for_verified(self):
        outreach.save_settings({"auto_send_email": True, "dry_run": True})
        settings = outreach.get_settings()

        job = {"results": [], "sent_count": 0, "lock": threading.Lock()}
        guessed_biz = providers.biz("g1", "Guessed Spa", category="salon", website="https://guessedspa.test", city="Austin")
        with (
            mock.patch("server.fetch_page", return_value=("<html><head><meta name='viewport' content='width=device-width'></head><body>Welcome to Guessed Spa, full website content here!</body></html>", "https://guessedspa.test", "Loads fine", True, 200, 0.4)),
            mock.patch("outreach.hunt_site_search_emails", return_value=[]),
            mock.patch("outreach.hunt_emails_without_website", return_value=([], [], "")),
        ):
            server.enrich(job, guessed_biz, settings)

        self.assertTrue(guessed_biz["email_guessed"])
        self.assertFalse(guessed_biz["email_verified"])
        self.assertEqual(guessed_biz["email_status"], "guessed")
        self.assertEqual(job["sent_count"], 0)

        verified_biz = providers.biz("v1", "Real Clinic", category="clinic", website="https://realclinic.test", city="Austin")
        with mock.patch(
            "server.fetch_page",
            return_value=("<html><body>Contact us at hello@realclinic.test for appointments and dental care in Austin.</body></html>", "https://realclinic.test", "Loads fine", True, 200, 0.5),
        ):
            server.enrich(job, verified_biz, settings)

        self.assertFalse(verified_biz["email_guessed"])
        self.assertTrue(verified_biz["email_verified"])
        self.assertEqual(verified_biz["email"], "hello@realclinic.test")
        self.assertEqual(verified_biz["email_status"], "simulated")
        self.assertEqual(job["sent_count"], 1)


class TestHttpEndpoints(IsolatedDataMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def _req(self, path, method="GET", payload=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_static_and_traversal_blocked(self):
        code, body = self._req("/")
        self.assertEqual(code, 200)
        self.assertIn("LeadFinder", body)

        code_trav, _ = self._req("/../server.py")
        self.assertEqual(code_trav, 404)

    def test_settings_redaction_and_unknown_post_404(self):
        code, body = self._req("/api/settings", method="POST", payload={"smtp_email": "me@x.test", "smtp_password": "top-secret-password"})
        self.assertEqual(code, 200)
        parsed = json.loads(body)
        self.assertEqual(parsed["settings"]["smtp_password"], "")
        self.assertTrue(parsed["settings"]["configured_secrets"]["smtp_password"])

        code_get, body_get = self._req("/api/settings")
        self.assertEqual(code_get, 200)
        self.assertNotIn("top-secret-password", body_get)

        code_404, _ = self._req("/api/nonexistent", method="POST", payload={})
        self.assertEqual(code_404, 404)

    def test_start_validation_and_job_polling(self):
        bad_code, _ = self._req("/api/start", method="POST", payload={"provider": "bogus", "city": "Austin", "category": "bakery"})
        self.assertEqual(bad_code, 400)

        missing_code, _ = self._req("/api/start", method="POST", payload={"provider": "osm", "city": "", "category": "bakery"})
        self.assertEqual(missing_code, 400)

        def fake_provider(p, log):
            log("Mocking OSM")
            yield providers.biz("mock1", "Mock Bakery", category="bakery", city="Austin", email="owner@mockbakery.test")

        with (
            mock.patch.dict(providers.PROVIDERS["osm"], {"fn": fake_provider}),
            mock.patch("server.discover_online", return_value=("", [], [])),
            mock.patch("outreach.hunt_emails_without_website", return_value=([], [], "")),
        ):
            code, body = self._req("/api/start", method="POST", payload={"provider": "osm", "city": "Austin", "category": "bakery"})
            self.assertEqual(code, 200)
            jid = json.loads(body)["id"]

            for _ in range(30):
                jcode, jbody = self._req(f"/api/job/{jid}?since=0")
                self.assertEqual(jcode, 200)
                jdata = json.loads(jbody)
                if jdata["done"]:
                    break
                time.sleep(0.05)

            self.assertTrue(jdata["done"])
            self.assertEqual(len(jdata["results"]), 1)
            self.assertEqual(jdata["results"][0]["name"], "Mock Bakery")
            self.assertTrue(jdata["results"][0]["email_verified"])

        bad_since, _ = self._req(f"/api/job/{jid}?since=-1")
        self.assertEqual(bad_since, 400)


if __name__ == "__main__":
    unittest.main()
