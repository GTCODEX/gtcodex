"""
Tests for the football_stats learning package.

Run from the repository root:

    python -m unittest tests.test_football_stats -v
"""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from football_stats import data as d
from football_stats import models as m
from football_stats import stats as st


class TestDescriptiveStatistics(unittest.TestCase):
    def test_mean_median_mode(self):
        self.assertEqual(st.mean([1, 2, 3, 4]), 2.5)
        self.assertEqual(st.median([1, 2, 3, 4]), 2.5)
        self.assertEqual(st.median([1, 2, 3]), 2)
        self.assertEqual(st.mode([1, 1, 2, 3]), 1)

    def test_variance_and_stdev(self):
        xs = [2, 4, 4, 4, 5, 5, 7, 9]
        self.assertAlmostEqual(st.mean(xs), 5.0)
        self.assertAlmostEqual(st.variance(xs), 32 / 7, places=10)  # sample variance
        self.assertAlmostEqual(st.stdev(xs), math.sqrt(32 / 7), places=10)

    def test_percentile_endpoints(self):
        xs = [1, 2, 3, 4, 5]
        self.assertEqual(st.percentile(xs, 0), 1)
        self.assertEqual(st.percentile(xs, 100), 5)
        self.assertEqual(st.percentile(xs, 50), 3)

    def test_histogram_counts_everything(self):
        xs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        hist = st.histogram(xs, bins=5)
        self.assertEqual(sum(c for _, _, c in hist), len(xs))

    def test_summary_keys(self):
        s = st.summary([1, 2, 3])
        for key in ("n", "mean", "median", "stdev", "min", "max", "p10", "p90"):
            self.assertIn(key, s)

    def test_empty_sequence_raises(self):
        with self.assertRaises(ValueError):
            st.mean([])


class TestDistributions(unittest.TestCase):
    def test_normal_cdf(self):
        self.assertAlmostEqual(st.normal_cdf(0.0), 0.5, places=12)
        self.assertAlmostEqual(st.normal_cdf(1.96), 0.9750021, places=6)
        self.assertAlmostEqual(st.normal_cdf(-1.96), 0.0249979, places=6)

    def test_normal_quantile_round_trip(self):
        for p in (0.01, 0.25, 0.5, 0.75, 0.99):
            self.assertAlmostEqual(st.normal_cdf(st.normal_quantile(p)), p, places=6)

    def test_t_cdf(self):
        self.assertAlmostEqual(st.t_cdf(0.0, 10), 0.5, places=12)
        self.assertAlmostEqual(st.t_cdf(2.0, 10), 0.9633064, places=6)
        # symmetry
        self.assertAlmostEqual(st.t_cdf(-1.5, 7), 1 - st.t_cdf(1.5, 7), places=12)

    def test_chi2_sf(self):
        self.assertAlmostEqual(st.chi2_sf(3.8414588, 1), 0.05, places=5)
        self.assertAlmostEqual(st.chi2_sf(0.0, 5), 1.0, places=12)

    def test_poisson_pmf_and_cdf(self):
        self.assertAlmostEqual(st.poisson_pmf(0, 1.0), math.exp(-1), places=12)
        self.assertAlmostEqual(st.poisson_cdf(2, 1.0), math.exp(-1) * 2.5, places=12)
        self.assertAlmostEqual(st.poisson_pmf(0, 0.0), 1.0, places=12)

    def test_fit_poisson_is_the_mean(self):
        self.assertAlmostEqual(st.fit_poisson([0, 1, 2, 3, 4]), 2.0, places=12)

    def test_poisson_probabilities_sum_to_one(self):
        total = sum(st.poisson_pmf(k, 2.5) for k in range(60))
        self.assertAlmostEqual(total, 1.0, places=10)


class TestInference(unittest.TestCase):
    def test_welch_ttest_detects_difference(self):
        a = [10, 11, 12, 11, 10, 12, 11, 10]
        b = [0, 1, 0, 1, 0, 1, 0, 1]
        result = st.welch_ttest(a, b)
        self.assertLess(result["p"], 0.001)

    def test_welch_ttest_identical_groups(self):
        a = [1, 2, 3, 4, 5]
        result = st.welch_ttest(a, list(a))
        self.assertAlmostEqual(result["t"], 0.0, places=12)
        self.assertEqual(result["p"], 1.0)

    def test_mannwhitneyu_known_value(self):
        a = [1, 2, 3, 4, 5]
        b = [6, 7, 8, 9, 10]
        result = st.mannwhitneyu(a, b)
        self.assertEqual(result["u"], 0.0)  # every b beats every a
        self.assertLess(result["p"], 0.01)

    def test_chi_square_gof_perfect_fit(self):
        result = st.chi_square_gof([10, 20, 30], [10, 20, 30])
        self.assertAlmostEqual(result["chi2"], 0.0, places=12)

    def test_bootstrap_ci_contains_mean(self):
        xs = list(range(1, 101))
        lo, hi = st.bootstrap_ci(xs, n_boot=1000, seed=1)
        self.assertLess(lo, st.mean(xs))
        self.assertGreater(hi, st.mean(xs))

    def test_ci_normal_mean(self):
        lo, hi = st.ci_normal_mean([1, 2, 3, 4, 5])
        self.assertLess(lo, 3.0)
        self.assertGreater(hi, 3.0)


class TestCorrelationAndRegression(unittest.TestCase):
    def test_pearson_perfect(self):
        self.assertAlmostEqual(st.pearson([1, 2, 3], [2, 4, 6]), 1.0, places=12)
        self.assertAlmostEqual(st.pearson([1, 2, 3], [6, 4, 2]), -1.0, places=12)

    def test_spearman_handles_ties(self):
        r = st.spearman([1, 2, 2, 4], [1, 2, 3, 4])
        self.assertGreater(r, 0.9)

    def test_linregress_recovers_line(self):
        x = list(range(20))
        y = [3 + 2 * v for v in x]
        reg = st.linregress(x, y)
        self.assertAlmostEqual(reg["intercept"], 3.0, places=8)
        self.assertAlmostEqual(reg["slope"], 2.0, places=8)
        self.assertAlmostEqual(reg["r2"], 1.0, places=8)

    def test_multiple_regression_recovers_coefficients(self):
        x1 = [i % 7 for i in range(100)]
        x2 = [(i * 3) % 5 for i in range(100)]
        y = [5 + 2 * a - 3 * b for a, b in zip(x1, x2)]
        reg = st.linear_regression(list(zip(x1, x2)), y)
        self.assertAlmostEqual(reg["coef"][0], 5.0, places=6)
        self.assertAlmostEqual(reg["coef"][1], 2.0, places=6)
        self.assertAlmostEqual(reg["coef"][2], -3.0, places=6)

    def test_logistic_regression_separates_classes(self):
        x = [[v] for v in range(-10, 10)]
        y = [0 if v < 0 else 1 for v in range(-10, 10)]
        fit = st.logistic_regression(x, y, lr=0.5, iters=4000)
        probs = [st.predict_logistic(fit["weights"], row) for row in x]
        self.assertLess(probs[0], 0.1)
        self.assertGreater(probs[-1], 0.9)


class TestEvaluationMetrics(unittest.TestCase):
    def test_brier_score(self):
        self.assertAlmostEqual(st.brier_score([1.0], [1]), 0.0, places=12)
        self.assertAlmostEqual(st.brier_score([0.0], [1]), 1.0, places=12)

    def test_log_loss(self):
        self.assertAlmostEqual(st.log_loss([1.0], [1]), 0.0, places=6)
        self.assertGreater(st.log_loss([0.5], [1]), st.log_loss([0.9], [1]))

    def test_roc_auc(self):
        self.assertAlmostEqual(st.roc_auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]), 1.0, places=12)
        self.assertAlmostEqual(st.roc_auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]), 0.0, places=12)

    def test_calibration_shape(self):
        rows = st.calibration([0.05, 0.95], [0, 1], bins=2)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["observed"], 0.0, places=12)
        self.assertAlmostEqual(rows[1]["observed"], 1.0, places=12)


class TestDataLayer(unittest.TestCase):
    def test_load_dataset(self):
        matches = d.load_dataset("epl_2018_19")
        self.assertEqual(len(matches), 380)
        self.assertEqual(len(d.team_names(matches)), 20)

    def test_team_name_normalisation(self):
        a = d.load_dataset("epl_2018_19")
        b = d.load_dataset("epl_2019_20")
        teams_a = set(d.team_names(a))
        teams_b = set(d.team_names(b))
        self.assertIn("Manchester City", teams_a)
        self.assertIn("Manchester City", teams_b)
        self.assertIn("Liverpool", teams_a & teams_b)

    def test_league_table_totals(self):
        matches = d.load_dataset("epl_2018_19")
        table = d.league_table(matches)
        self.assertEqual(sum(r["p"] for r in table), 760)  # 380 matches x 2 teams
        self.assertEqual(table[0]["team"], "Manchester City")
        self.assertEqual(table[0]["pts"], 98)

    def test_split_by_date_is_chronological(self):
        matches = d.load_dataset("epl_2018_19")
        train, test = d.split_by_date(matches, 0.5)
        self.assertEqual(len(train), 190)
        self.assertLessEqual(max(m.date for m in train), min(m.date for m in test))

    def test_match_result_and_total(self):
        m = d.Match(date="2020-01-01", home="A", away="B", home_goals=2, away_goals=1)
        self.assertEqual(m.result, "H")
        self.assertEqual(m.total_goals, 3)
        self.assertTrue(m.btts)

    def test_round_robin_schedule_size(self):
        schedule = d.round_robin_schedule([f"T{i}" for i in range(20)])
        self.assertEqual(len(schedule), 380)  # 20 teams x 19 opponents x 2 legs


class TestPoissonModel(unittest.TestCase):
    def test_fit_reproduces_goal_totals(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        exp_home = sum(model.lambdas(x.home, x.away)[0] for x in matches)
        exp_away = sum(model.lambdas(x.home, x.away)[1] for x in matches)
        self.assertAlmostEqual(exp_home, sum(x.home_goals for x in matches), places=6)
        self.assertAlmostEqual(exp_away, sum(x.away_goals for x in matches), places=6)

    def test_match_probabilities_sum_to_one(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        p = model.match_probabilities("Arsenal", "Chelsea")
        # the score matrix is truncated at 10 goals, so allow a tiny tail mass
        self.assertAlmostEqual(p["home_win"] + p["draw"] + p["away_win"], 1.0, places=5)
        self.assertGreater(p["home_win"], p["away_win"])

    def test_better_team_has_higher_win_probability(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        top = model.ratings_table()[0]["team"]
        bottom = model.ratings_table()[-1]["team"]
        p = model.match_probabilities(top, bottom)
        self.assertGreater(p["home_win"], 0.5)
        self.assertGreater(p["home_win"], p["away_win"])

    def test_unseen_team_falls_back_to_average(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        lh, la = model.lambdas("Arsenal", "A Team That Does Not Exist")
        self.assertGreater(lh, 0)
        self.assertGreater(la, 0)

    def test_baseline_probabilities_sum_to_one(self):
        matches = d.load_dataset("epl_2018_19")
        baseline = m.fit_baseline(matches)
        p = baseline.match_probabilities("Arsenal", "Chelsea")
        self.assertAlmostEqual(p["home_win"] + p["draw"] + p["away_win"], 1.0, places=5)

    def test_poisson_model_beats_baseline_on_held_out_half(self):
        matches = d.load_dataset("epl_2018_19")
        train, test = d.split_by_date(matches, 0.5)
        model = m.fit_poisson(train, fit_rho=False)
        baseline = m.fit_baseline(train)

        def log_loss(predict):
            losses = []
            for x in test:
                p = predict(x.home, x.away)
                losses.append(-math.log(max({"H": p["home_win"], "D": p["draw"],
                                             "A": p["away_win"]}[x.result], 1e-15)))
            return st.mean(losses)

        self.assertLess(log_loss(model.match_probabilities),
                        log_loss(baseline.match_probabilities))


class TestElo(unittest.TestCase):
    def test_expected_score_bounds(self):
        elo = m.Elo()
        e = elo.expected("A", "B")
        self.assertGreater(e, 0.5)  # home advantage
        self.assertLess(e, 1.0)

    def test_update_moves_ratings(self):
        elo = m.Elo(k=20)
        before = elo.rating("A")
        elo.update(d.Match(date="2020-01-01", home="A", away="B", home_goals=3, away_goals=0))
        self.assertGreater(elo.rating("A"), before)
        self.assertLess(elo.rating("B"), before)

    def test_elo_fit_produces_table(self):
        matches = d.load_dataset("epl_2018_19")
        table = m.Elo(k=20).fit(matches).table()
        self.assertEqual(len(table), 20)
        self.assertEqual(table[0]["team"], "Manchester City")

    def test_elo_ratings_sum_to_constant(self):
        matches = d.load_dataset("epl_2018_19")
        elo = m.Elo(k=20).fit(matches)
        self.assertAlmostEqual(sum(r["rating"] for r in elo.table()), 1500 * 20, places=6)


class TestSimulation(unittest.TestCase):
    def test_simulate_matches_shape(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        fixtures = [("Arsenal", "Chelsea"), ("Liverpool", "Everton")]
        sim = m.simulate_matches(model, fixtures, seed=3)
        self.assertEqual(len(sim), 2)
        self.assertGreaterEqual(sim[0].home_goals, 0)

    def test_simulate_season_probabilities_sum_to_one(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        teams = d.team_names(matches)
        result = m.simulate_season(model, teams, n_sim=200, seed=11)
        self.assertAlmostEqual(sum(result["title_prob"].values()), 1.0, places=6)

    def test_simulation_is_reproducible(self):
        matches = d.load_dataset("epl_2018_19")
        model = m.fit_poisson(matches)
        a = m.simulate_matches(model, [("Arsenal", "Chelsea")], seed=5)
        b = m.simulate_matches(model, [("Arsenal", "Chelsea")], seed=5)
        self.assertEqual((a[0].home_goals, a[0].away_goals),
                         (b[0].home_goals, b[0].away_goals))


if __name__ == "__main__":
    unittest.main()
