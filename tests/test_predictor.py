"""Tests for the outcome predictor and its honest evaluation."""
import json
import math
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server
from football_stats import data as d
from football_stats import predictor as p


class TestOddsConversion(unittest.TestCase):
    def test_odds_to_probs_sums_to_one(self):
        probs = p.odds_to_probs(2.0, 3.5, 3.6)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=12)

    def test_odds_to_probs_favourite(self):
        probs = p.odds_to_probs(1.30, 5.00, 9.00)
        self.assertGreater(probs["H"], probs["D"])
        self.assertGreater(probs["D"], probs["A"])

    def test_over_under_probs(self):
        probs = p.over_under_probs(1.9, 1.95)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=12)


class TestEloSignal(unittest.TestCase):
    def test_probs_sum_to_one(self):
        matches = d.load_dataset("epl_2018_19")[:200]
        sig = p.fit_elo_signal(matches)
        probs = sig.probs("Arsenal", "Chelsea")
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=10)

    def test_better_team_favoured(self):
        matches = d.load_dataset("epl_2018_19")
        sig = p.fit_elo_signal(matches)
        top = max(sig.elo.ratings, key=lambda t: sig.elo.ratings[t])
        bottom = min(sig.elo.ratings, key=lambda t: sig.elo.ratings[t])
        probs = sig.probs(top, bottom)
        self.assertGreater(probs["H"], probs["A"])


class TestPredictor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matches = d.load_dataset("epl_2018_19")
        cls.predictor = p.fit_predictor(cls.matches,
                                        config=p.PredictorConfig(holdout_frac=0.25))

    def test_prediction_probabilities_valid(self):
        pred = self.predictor.predict("Arsenal", "Chelsea")
        self.assertAlmostEqual(pred.home_win + pred.draw + pred.away_win, 1.0, places=6)
        for value in (pred.home_win, pred.draw, pred.away_win):
            self.assertGreater(value, 0.0)
            self.assertLess(value, 1.0)

    def test_prediction_with_odds_is_calibrated(self):
        pred = self.predictor.predict("Arsenal", "Chelsea", odds=(2.10, 3.40, 3.60))
        self.assertAlmostEqual(pred.home_win + pred.draw + pred.away_win, 1.0, places=6)
        self.assertIn("odds", pred.source)

    def test_summary_mentions_teams(self):
        text = self.predictor.predict("Arsenal", "Chelsea").summary()
        self.assertIn("Arsenal", text)
        self.assertIn("Chelsea", text)

    def test_unseen_team_is_handled(self):
        pred = self.predictor.predict("Arsenal", "Nonexistent FC")
        self.assertAlmostEqual(pred.home_win + pred.draw + pred.away_win, 1.0, places=6)

    def test_prediction_is_deterministic(self):
        a = self.predictor.predict("Liverpool", "Everton")
        b = self.predictor.predict("Liverpool", "Everton")
        self.assertAlmostEqual(a.home_win, b.home_win, places=12)


class TestEvaluation(unittest.TestCase):
    def test_wilson_ci_contains_estimate(self):
        lo, hi = p.wilson_ci(60, 100)
        self.assertLess(lo, 0.6)
        self.assertGreater(hi, 0.6)

    def test_wilson_ci_endpoints(self):
        self.assertEqual(p.wilson_ci(0, 0), (0.0, 0.0))
        lo, hi = p.wilson_ci(100, 100)
        self.assertGreater(lo, 0.9)
        self.assertEqual(hi, 1.0)

    def test_accuracy_report_perfect_predictions(self):
        matches = d.load_dataset("epl_2018_19")[:30]
        preds = []
        for m in matches:
            pred = p.Prediction(home=m.home, away=m.away,
                                home_win=1.0 if m.result == "H" else 0.0,
                                draw=1.0 if m.result == "D" else 0.0,
                                away_win=1.0 if m.result == "A" else 0.0)
            preds.append(pred)
        report = p.accuracy_report(preds, matches)
        self.assertAlmostEqual(report["accuracy"], 1.0, places=12)
        self.assertAlmostEqual(report["log_loss"], 0.0, places=6)

    def test_compare_with_market(self):
        matches = d.load_dataset("epl_2018_19")[:100]
        predictor = p.fit_predictor(matches, config=p.PredictorConfig(holdout_frac=0.2))
        preds = predictor.predict_many(matches)
        vs = p.compare_with_market(preds, matches)
        self.assertGreater(vs["n"], 0)
        self.assertGreater(vs["model_log_loss"], 0)


class TestBacktest(unittest.TestCase):
    def test_backtest_runs_and_reports(self):
        matches = d.load_dataset("epl_2018_19")
        report = p.backtest(matches, min_train=190, step=190,
                            config=p.PredictorConfig(holdout_frac=0.2),
                            verbose=False)
        self.assertGreater(report["n"], 0)
        self.assertGreaterEqual(report["accuracy"], 0.0)
        self.assertLessEqual(report["accuracy"], 1.0)
        self.assertGreater(report["log_loss"], 0.0)
        self.assertEqual(len(report["predictions"]), report["n"])


class TestDecayAndRidge(unittest.TestCase):
    def test_decay_changes_the_fit(self):
        matches = d.load_dataset("epl_2018_19")
        from football_stats import models as m
        plain = m.fit_poisson(matches[:300], decay=1.0, ridge=0.0, fit_rho=False)
        decayed = m.fit_poisson(matches[:300], decay=0.95, ridge=0.0, fit_rho=False)
        self.assertNotEqual(plain.mu, decayed.mu)

    def test_ridge_shrinks_ratings(self):
        matches = d.load_dataset("epl_2018_19")[:200]
        from football_stats import models as m
        plain = m.fit_poisson(matches, ridge=0.0, fit_rho=False)
        shrunk = m.fit_poisson(matches, ridge=0.5, fit_rho=False)
        spread_plain = max(plain.attack.values()) - min(plain.attack.values())
        spread_shrunk = max(shrunk.attack.values()) - min(shrunk.attack.values())
        self.assertLess(spread_shrunk, spread_plain)


class TestPredictorEndpoints(unittest.TestCase):
    """The dashboard's API, served by the same handler as LeadFinder."""

    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _req(self, path, method="GET", payload=None, timeout=120):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_predictor_page_is_served(self):
        code, body = self._req("/predictor.html")
        self.assertEqual(code, 200)
        self.assertIn("Match Outcome Predictor", body)

    def test_datasets_endpoint_lists_both_seasons(self):
        code, body = self._req("/api/predictor/datasets")
        self.assertEqual(code, 200)
        payload = json.loads(body)
        ids = {x["id"] for x in payload}
        self.assertEqual(ids, {"epl_2018_19", "epl_2019_20"})
        self.assertTrue(all(len(x["teams"]) == 20 for x in payload))

    def test_teams_endpoint(self):
        code, body = self._req("/api/predictor/teams?dataset=epl_2018_19")
        self.assertEqual(code, 200)
        self.assertIn("Arsenal", json.loads(body)["teams"])

    def test_teams_endpoint_rejects_unknown_dataset(self):
        code, _ = self._req("/api/predictor/teams?dataset=nope")
        self.assertEqual(code, 400)

    def test_predict_endpoint(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19",
                                        "home": "Arsenal", "away": "Chelsea"})
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertAlmostEqual(payload["home_win"] + payload["draw"]
                               + payload["away_win"], 1.0, places=4)
        self.assertIn(payload["most_likely_outcome"], ("H", "D", "A"))

    def test_predict_endpoint_blends_odds(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19", "home": "Arsenal",
                                        "away": "Chelsea", "odds": [2.1, 3.4, 3.6]})
        self.assertEqual(code, 200)
        self.assertIn("odds", json.loads(body)["source"])

    def test_predict_endpoint_validation(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19",
                                        "home": "Arsenal", "away": "Arsenal"})
        self.assertEqual(code, 400)
        self.assertIn("different", json.loads(body)["error"])

        code2, _ = self._req("/api/predictor/predict", method="POST", payload={})
        self.assertEqual(code2, 400)


if __name__ == "__main__":
    unittest.main()
