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
├── predictor.py            # ensemble outcome predictor + walk-forward backtesting
├── predict.py              # command-line predictor: python -m football_stats.predict
├── prediction_log.py       # record forecasts, settle them, score the log
├── fetch.py                # re-download the original public datasets from GitHub
├── prepare.py              # rebuild the recent-season datasets from those sources
├── datasets/
│   ├── epl_2018_19.csv     # 380 matches, with xG, shots, possession, cards, odds
│   ├── epl_2019_20.csv     # 380 matches, with shots, cards, fouls, odds
│   ├── epl_2025_26.csv     # 380 matches, complete season with half-time scores
│   ├── epl_2026_27.csv     # current season, refreshed daily (shots, corners, cards)
│   ├── supplement_2026_27.csv  # played matches the source has not published yet
│   └── README.md           # provenance and column dictionary
├── examples/
│   ├── 01_descriptive_statistics.py
│   ├── 02_poisson_distribution.py
│   ├── 03_home_advantage.py
│   ├── 04_correlation_regression.py
│   ├── 05_expected_goals.py
│   ├── 06_poisson_match_prediction.py
│   ├── 07_elo_ratings.py
│   ├── 08_predicting_a_new_season.py
│   ├── 09_outcome_predictor.py
│   └── 10_forecast_log.py
├── CURRICULUM.md           # the full course
└── README.md
```

## Predict a match right now

```bash
cd /home/user/gtcodex

python -m football_stats.predict "Arsenal" "Chelsea" --dataset epl_recent
python -m football_stats.predict "Arsenal" "Chelsea" --odds 2.10 3.40 3.60
python -m football_stats.predict --backtest --dataset epl_recent
python -m football_stats.predict --season epl_2019_20 --train epl_2018_19
```

`--dataset epl_recent` fits on the 2025/26 season plus everything played so far in
2026/27, which is the right training set for a current fixture.

The predictor blends a Poisson model, Elo ratings and (when supplied) the bookmaker's
odds. Blend weights are tuned on held-out data and the probabilities are calibrated.

### Keeping score

A backtest is not the same as a record of what you actually forecast. The prediction
log writes every forecast down before the match and scores it afterwards:

```bash
python -m football_stats.predict "Liverpool" "Manchester United" --dataset epl_recent \
    --date 2026-11-22 --log
python -m football_stats.prediction_log --settle   # fill in results once played
python -m football_stats.prediction_log            # the honest scorecard
```

The log lives at `data/prediction_log.json` and is surfaced on the dashboard's
**Forecast log** tab.

### Refreshing the data

The current season changes daily:

```bash
python -m football_stats.prepare            # rebuild epl_2025_26 + epl_2026_27
python -m football_stats.fetch              # only re-download the raw sources
```

If a match has been played but the source has not caught up, add it to
`datasets/supplement_2026_27.csv` — the builder merges it in.

Or use the web dashboard: `python server.py`, then open `/predictor.html`.

## The nine lessons

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
| 9 | The outcome predictor | ensemble blending, calibration, walk-forward backtesting |
| 10 | The forecast log | pre-registering forecasts, settling results, calibration error |

## API map

```python
from football_stats import data as d, stats as st, models as m, predictor as p

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
model = m.fit_poisson(train, decay=0.99, ridge=0.001)
model.lambdas("Arsenal", "Chelsea")          # -> (expected home goals, expected away goals)
model.match_probabilities("Arsenal", "Chelsea")
elo = m.Elo(k=20, home_advantage=100).fit(matches)
m.simulate_season(model, teams, n_sim=2000, seed=7)

# --- prediction ---------------------------------------------------------
predictor = p.fit_predictor(train)            # Poisson + Elo (+ odds), tuned & calibrated
predictor.predict("Arsenal", "Chelsea")      # -> Prediction with 1X2, O/U, BTTS, score
predictor.predict("Arsenal", "Chelsea", odds=(2.10, 3.40, 3.60))
report = p.backtest(train)                   # walk-forward accuracy, log-loss, vs market
p.predict_season(train, season)              # predict a whole season
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
