import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import outreach
import providers
import server


class TestVercelRuntime(unittest.TestCase):
    def test_health_reports_runtime(self):
        code, body, ctype = server.dispatch("GET", "/api/health", serverless=True)
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "application/json")
        self.assertTrue(body["ok"])
        self.assertEqual(body["runtime"], "vercel")
        self.assertEqual(body["storage"], "ephemeral")

    def test_static_fallback_still_works(self):
        code, body, ctype = server.dispatch("GET", "/", serverless=True)
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "text/html")
        self.assertIn(b"LeadFinder", body)

    def test_serverless_start_returns_results_without_polling(self):
        def fake_provider(p, set_msg):
            set_msg("Mocking OSM")
            yield providers.biz("v1", "Vercel Bakery", category="bakery", city="Jos")
            yield providers.biz("v2", "Vercel Clinic", category="clinic", city="Jos")

        def fake_enrich(job, business, settings):
            with job["lock"]:
                job["results"].append({"id": business["id"], "name": business["name"]})

        payload = json.dumps({"provider": "osm", "city": "Jos", "category": "bakery"}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(server, "JOBS_DIR", Path(tmp) / "jobs"),
                mock.patch.object(server, "SERVERLESS_MAX_LEADS", 2),
                mock.patch.object(outreach, "get_settings", return_value={}),
                mock.patch.object(server, "enrich", fake_enrich),
                mock.patch.dict(providers.PROVIDERS["osm"], {"fn": fake_provider}),
            ):
                code, body, ctype = server.dispatch("POST", "/api/start", payload, serverless=True)

        self.assertEqual(code, 200)
        self.assertEqual(ctype, "application/json")
        self.assertEqual(body["runtime"], "vercel")
        self.assertTrue(body["done"])
        self.assertEqual(body["found"], 2)
        self.assertEqual(len(body["results"]), 2)
        self.assertIn("id", body)
        server.JOBS.pop(body["id"], None)

    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask is not installed")
    def test_flask_wrapper_serves_health_and_dashboard(self):
        import app

        client = app.app.test_client()
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["runtime"], "vercel")

        home = client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"LeadFinder", home.data)


if __name__ == "__main__":
    unittest.main()
