# ⚽ football_stats — Statistics Analysis of Football Data

A zero-dependency learning package for statistical analysis of football (soccer) data,
built to match this repository's pure-stdlib convention.

> **New here?** Start with **[CURRICULUM.md](CURRICULUM.md)** — a complete eight-lesson
> course with exercises, real data, and runnable code.

---

## Quick start

```bash
cd /home/user/gtcodex

# Lesson 1 — describe a season
python -m football_stats.examples.01_descriptive_statistics

# Lesson 6 — predict matches and evaluate against the bookmaker
python -m football_stats.examples.06_poisson_match_prediction

# Run the tests
python -m unittest tests.test_football_stats -v
```

Requires only Python 3.10+.

## What's inside

```
football_stats/
├── data.py                 # load tidy CSVs, league tables, splits, name normalisation
├── stats.py                # descriptive stats, distributions, tests, regression, scoring
├── models.py               # Poisson match model, Elo ratings, Monte-Carlo simulation
├── fetch.py                # re-download the original public datasets from GitHub
├── datasets/
│   ├── epl_2018_19.csv     # 380 matches, with xG, shots, possession, cards, odds
│   ├── epl_2019_20.csv     # 380 matches, with shots, cards, fouls, odds
│   └── README.md           # provenance and column dictionary
├── examples/
│   ├── 01_descriptive_statistics.py
│   ├── 02_poisson_distribution.py
│   ├── 03_home_advantage.py
│   ├── 04_correlation_regression.py
│   ├── 05_expected_goals.py
│   ├── 06_poisson_match_prediction.py
│   ├── 07_elo_ratings.py
│   └── 08_predicting_a_new_season.py
├── CURRICULUM.md           # the full course
└── README.md
```

## The eight lessons

| # | Lesson | Statistical ideas |
|---|--------|-------------------|
| 1 | Descriptive statistics | mean, median, spread, percentiles, histograms, league tables |
| 2 | The Poisson distribution | probability mass functions, maximum likelihood, chi-square GOF |
| 3 | Home advantage | confidence intervals, bootstrap, t-test, Mann-Whitney, effect size |
| 4 | Correlation & regression | Pearson/Spearman, OLS, R², logistic regression, multicollinearity |
| 5 | Expected goals (xG) | chance quality, calibration, out-of-sample prediction |
| 6 | Match prediction | Poisson model, Dixon-Coles adjustment, log-loss, overfitting |
| 7 | Elo ratings | rating systems, expected score, K-factor, home advantage |
| 8 | New seasons & simulation | cross-season testing, Monte-Carlo, title probabilities |

## API map

```python
from football_stats import data as d, stats as st, models as m

# --- data ---------------------------------------------------------------
matches = d.load_dataset("epl_2018_19")     # list[Match]
train, test = d.split_by_date(matches, 0.5)  # chronological split
table = d.league_table(matches)              # standings
ha = d.home_advantage(matches)               # home/away summary

# --- stats --------------------------------------------------------------
st.summary([1, 2, 3])                        # mean/median/sd/percentiles
st.pearson(x, y); st.spearman(x, y)
reg = st.linregress(x, y)                    # slope, intercept, r2, p
st.welch_ttest(a, b); st.mannwhitneyu(a, b)
st.bootstrap_ci(xs)
st.chi_square_gof(observed, expected)
st.brier_score(probs, outcomes); st.log_loss(probs, outcomes)
st.roc_auc(scores, labels)

# --- models -------------------------------------------------------------
model = m.fit_poisson(train)                 # attack/defence ratings + home advantage
model.lambdas("Arsenal", "Chelsea")          # -> (expected home goals, expected away goals)
model.match_probabilities("Arsenal", "Chelsea")
elo = m.Elo(k=20, home_advantage=100).fit(matches)
m.simulate_season(model, teams, n_sim=2000, seed=7)
```

## Design notes

- **Zero dependencies.** Every algorithm is implemented in the standard library and is
  small enough to read. You can see exactly how a t-test p-value or a Poisson model
  works — no black boxes.
- **Real data.** Both datasets come from public sources and match the official records
  (2018/19: 1,072 goals, Man City 98 points; 2019/20: 1,034 goals, Liverpool 99 points).
- **Honest evaluation.** Every model is judged on held-out data, against a naive
  baseline and (where available) against the betting market.
- **Teaching first.** Functions are simple and composable; the examples are written to
  be read top-to-bottom.

## Contributing

Exercises, new lessons, new datasets and fixes are welcome. See the repository's
contributing guidelines. If you add a dataset, please document its source and licence
in `datasets/README.md`.
