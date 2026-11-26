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


class TestPredictorFitting(unittest.TestCase):
    """Regression tests for problems found when checking the predictions."""

    @classmethod
    def setUpClass(cls):
        cls.matches = d.load_dataset("epl_2018_19")

    def test_config_is_not_mutated(self):
        cfg = p.PredictorConfig()
        before = (cfg.poisson_weight, cfg.elo_weight, cfg.odds_weight, cfg.poisson_share)
        p.fit_predictor(self.matches, config=cfg)
        self.assertEqual(before, (cfg.poisson_weight, cfg.elo_weight,
                                  cfg.odds_weight, cfg.poisson_share))

    def test_refit_uses_every_training_match(self):
        pred = p.fit_predictor(self.matches)
        self.assertEqual(pred.n_train, len(self.matches))
        self.assertEqual(pred.poisson.n_matches, len(self.matches))
        self.assertEqual(len(pred.elo.elo.history), len(self.matches))
        old = p.fit_predictor(self.matches, config=p.PredictorConfig(refit=False))
        self.assertLess(old.n_train, len(self.matches))

    def test_market_only_weights_do_not_crash_without_odds(self):
        # The tuner can give the market all the weight; predicting without odds
        # used to divide by zero.
        pred = p.fit_predictor(self.matches)
        pred.config.odds_weight = 1.0
        pred.config.poisson_weight = pred.config.elo_weight = 0.0
        out = pred.predict("Arsenal", "Chelsea")
        self.assertAlmostEqual(out.home_win + out.draw + out.away_win, 1.0, places=6)
        self.assertNotIn("odds", out.source)

    def test_backtest_without_odds(self):
        report = p.backtest(self.matches, min_train=300, step=40, use_odds=False,
                            verbose=False)
        self.assertEqual(report["n"], 80)
        self.assertTrue(all("odds" not in x.source for x in report["predictions"]))

    def test_zero_weight_signal_not_reported(self):
        pred = p.fit_predictor(self.matches)
        pred.config.poisson_share = 1.0
        out = pred.predict("Arsenal", "Chelsea")
        self.assertEqual(out.source, "poisson")


class TestTeamResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = p.fit_predictor(d.load_dataset("epl_2018_19"))

    def test_common_names_resolve(self):
        cases = {"Man City": "Manchester City", "man utd": "Manchester United",
                 "Spurs": "Tottenham Hotspur", "huddersfield": "Huddersfield Town",
                 "Wolves": "Wolverhampton Wanderers", " Chelsea ": "Chelsea",
                 "brighton and hove albion": "Brighton & Hove Albion"}
        for given, expected in cases.items():
            self.assertEqual(self.predictor.resolve_team(given), expected, given)

    def test_typo_is_rejected_with_suggestion(self):
        with self.assertRaises(p.UnknownTeamError) as ctx:
            self.predictor.resolve_team("Arsenl")
        self.assertIn("Arsenal", ctx.exception.suggestions)

    def test_ambiguous_prefix_is_rejected(self):
        with self.assertRaises(p.UnknownTeamError) as ctx:
            self.predictor.resolve_team("Manchester")
        self.assertIn("Manchester City", ctx.exception.suggestions)
        self.assertIn("Manchester United", ctx.exception.suggestions)

    def test_alias_gives_same_prediction_as_full_name(self):
        a = self.predictor.predict("Man City", "Huddersfield")
        b = self.predictor.predict("Manchester City", "Huddersfield Town")
        self.assertAlmostEqual(a.home_win, b.home_win, places=12)
        self.assertGreater(a.home_win, 0.8)  # was ~45% when the names went unrecognised

    def test_unseen_team_is_flagged(self):
        out = self.predictor.predict("Norwich City", "Chelsea")
        self.assertIn("Norwich City", out.advice)
        self.assertIn("not in the training data", out.advice)

    def test_unseen_team_gets_promoted_prior(self):
        # A promoted side is rated like the weakest teams, not like an average one.
        avg = p.fit_predictor(d.load_dataset("epl_2018_19"),
                              config=p.PredictorConfig(promoted_prior=0.0))
        weak = self.predictor.predict("Liverpool", "Norwich City").home_win
        flat = avg.predict("Liverpool", "Norwich City").home_win
        self.assertGreater(weak, flat)
        self.assertIn("league-average", avg.predict("Liverpool", "Norwich City").advice)
        prior = self.predictor.diagnostics["unseen_team_prior"]
        self.assertLess(prior["attack"], 0.0)
        self.assertLess(prior["defence"], 0.0)
        self.assertLess(prior["elo"], 1500.0)

    def test_predicting_unseen_team_does_not_mutate_model(self):
        before = dict(self.predictor.elo.elo.ratings)
        self.predictor.predict("Some New FC", "Chelsea")
        self.assertEqual(before, self.predictor.elo.elo.ratings)


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

    def test_predict_endpoint_rejects_unknown_team(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19",
                                        "home": "Arsenl", "away": "Chelsea"})
        self.assertEqual(code, 400)
        payload = json.loads(body)
        self.assertIn("Unknown team", payload["error"])
        self.assertIn("Arsenal", payload["suggestions"])

    def test_predict_endpoint_resolves_aliases(self):
        code, body = self._req("/api/predictor/predict", method="POST",
                               payload={"dataset": "epl_2018_19",
                                        "home": "Man City", "away": "Spurs"})
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual(payload["home"], "Manchester City")
        self.assertEqual(payload["away"], "Tottenham Hotspur")


if __name__ == "__main__":
    unittest.main()
