"""Tests for the outcome predictor and its honest evaluation."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


if __name__ == "__main__":
    unittest.main()
