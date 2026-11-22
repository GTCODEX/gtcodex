# Statistics Analysis of Football Data — Learning Curriculum

A hands-on course in statistical analysis using real football (soccer) data. You will
learn the statistics *and* how to apply them, by writing and running code on two full
Premier League seasons.

Everything here is pure Python 3.10+ standard library — the same zero-dependency
philosophy as the rest of this repository. No pandas, no numpy, no scipy, no paid data.

---

## Who this is for

- You know basic Python (variables, loops, functions, lists/dicts).
- You have heard of mean, standard deviation and probability, but want to actually use them.
- You like football and want to answer real questions with data.

You do **not** need A-level statistics, a maths degree, or any football-analytics
experience. Every concept is introduced in the context of a question you already care
about ("Is home advantage real?", "Who will win this match?").

## How to use this course

Work through the eight lessons in order. Each lesson is a runnable script:

```bash
cd /home/user/gtcodex
python -m football_stats.examples.01_descriptive_statistics
python -m football_stats.examples.02_poisson_distribution
python -m football_stats.examples.03_home_advantage
python -m football_stats.examples.04_correlation_regression
python -m football_stats.examples.05_expected_goals
python -m football_stats.examples.06_poisson_match_prediction
python -m football_stats.examples.07_elo_ratings
python -m football_stats.examples.08_predicting_a_new_season
```

Each script prints a report, explains what it just did, and ends with **"Your turn"**
exercises. Do the exercises — that is where the learning happens. A suggested pacing:

| Day | Lesson | Focus |
|-----|--------|-------|
| 1 | 1, 2 | Describing data; the Poisson distribution |
| 2 | 3, 4 | Hypothesis tests; correlation and regression |
| 3 | 5, 6 | Expected goals; building and judging a prediction model |
| 4 | 7, 8 | Elo ratings; cross-season prediction and simulation |
| 5 | Capstone | Your own analysis (see below) |

---

## The data

Two tidy CSV files, one row per match, in `football_stats/datasets/`:

| File | Season | Matches | Extras |
|------|--------|---------|--------|
| `epl_2018_19.csv` | 2018/19 Premier League | 380 | xG, shots, shots on target, possession, corners, cards, odds |
| `epl_2019_20.csv` | 2019/20 Premier League | 380 | shots, shots on target, corners, fouls, cards, half-time score, odds |

Both are derived from public sources (see `datasets/README.md`) and were checked
against the official records: 2018/19 had 1,072 goals and Manchester City won with
98 points; 2019/20 had 1,034 goals and Liverpool won with 99 points.

Load them with:

```python
from football_stats import data as d

matches = d.load_dataset("epl_2018_19")   # -> list of Match
matches[0]
# Match(date='2018-08-10', home='Manchester United', away='Leicester City',
#       home_goals=2, away_goals=1, stats={'home_xg': '1.25', ...})
```

---

## Module 1 — Describing data (Lesson 1)

**Question:** what does a football season actually look like?

**Concepts:** mean, median, mode, variance, standard deviation, percentiles,
histograms, skew, league tables.

**Run:** `python -m football_stats.examples.01_descriptive_statistics`

**What you learn:**
- The mean and median answer different questions; football goals are concentrated at
  1–3 with a long right tail.
- League tables are just grouped aggregations of match results.
- 2018/19 in one line: 2.82 goals per game, home teams scored 1.57 vs 1.25 for away
  teams, home win 47.6% / draw 18.7% / away win 33.7%.

**Exercises to try:**
- Compute the interquartile range of total goals.
- Which is more variable: home goals or away goals?
- Re-run everything for 2019/20 and write down three differences.

---

## Module 2 — Probability distributions (Lesson 2)

**Question:** can we model the number of goals with a simple probability distribution?

**Concepts:** random variables, the Poisson distribution, maximum likelihood
(lambda = the mean), probability mass functions, cumulative probabilities,
chi-square goodness of fit.

**Run:** `python -m football_stats.examples.02_poisson_distribution`

**What you learn:**
- Goals are counts, so the Poisson distribution is the natural first model:
  `P(X = k) = e^{-λ} λ^k / k!`.
- Fitting the model means choosing lambda; the maximum-likelihood estimate is the
  sample mean (2.821 for total goals in 2018/19).
- You can test the model: the chi-square test compares observed and expected
  frequencies. Here `p = 0.82`, so a single Poisson describes total goals well.

**Exercises to try:**
- Fit a Poisson to home goals only and repeat the test.
- Compute P(exactly 3 goals) for the away team.
- What extra parameter would you add to handle over-dispersion? (Hint: negative binomial.)

---

## Module 3 — Inference: comparing two groups (Lesson 3)

**Question:** is home advantage real, or just noise?

**Concepts:** null and alternative hypotheses, confidence intervals, bootstrapping,
Welch's t-test, Mann-Whitney U test, p-values, effect size (Cohen's d).

**Run:** `python -m football_stats.examples.03_home_advantage`

**What you learn:**
- A 95% bootstrap confidence interval for the home–away goal difference is
  [0.13, 0.51]: it excludes zero, so the advantage is unlikely to be chance.
- Welch's t-test (assumes roughly normal groups) and Mann-Whitney (assumes nothing)
  both give `p < 0.001`. Different assumptions, same conclusion — that is reassuring.
- Effect size matters: Cohen's d = 0.25 is *small*. Home advantage is real but modest.
- In points terms, home teams earned 1.62 per game vs 1.20 for away teams.

**Exercises to try:**
- Repeat for 2019/20 (note: the COVID-19 shutdown meant matches behind closed doors —
  what happens to home advantage?).
- Compare the home advantage of the top 6 vs the bottom 6 teams.
- Bootstrap the home-win percentage instead of the goal difference.

---

## Module 4 — Correlation and regression (Lesson 4)

**Question:** which statistics actually predict goals?

**Concepts:** Pearson vs Spearman correlation, simple and multiple linear regression,
least squares, R-squared, p-values for slopes, logistic regression, multicollinearity.

**Run:** `python -m football_stats.examples.04_correlation_regression`

**What you learn:**
- Correlation with goals in 2018/19: shots on target **0.59**, xG **0.44**,
  shots **0.40**, possession **0.24**. Quality beats quantity; possession is weak.
- `goals = 0.186 + 0.122 × shots`, R² = 0.16: each shot adds about 0.12 goals, but
  shots explain only 16% of the variation — football is noisy.
- In a multiple regression with xG, the shots coefficient flips sign. That is
  multicollinearity: two variables carrying the same information.
- Logistic regression on (xG difference, possession difference) predicts the home win
  with ROC-AUC 0.71 — useful, not clairvoyant.

**Exercises to try:**
- Repeat the regressions for away teams.
- Add a home/away dummy variable to the regression.
- Compute the correlation between xG difference and the result.

---

## Module 5 — Expected goals (Lesson 5)

**Question:** what is xG, and why do analysts trust it more than goals?

**Concepts:** expected goals, chance quality, calibration, out-of-sample prediction,
the difference between describing and predicting.

**Run:** `python -m football_stats.examples.05_expected_goals`

**What you learn:**
- xG and goals agree on average (2.80 vs 2.82 per match) but not match by match.
- The real test is prediction: using the first half of the season to predict the second,
  xG (MAE 0.98) and shots on target (MAE 0.98) beat past goals (MAE 1.23). Chance
  quality is a better guide to the future than the scoreline.
- Calibration: bin matches by total xG and compare with actual goals. Close agreement
  means the xG model means what it says.
- You can price a match directly from xG with two Poisson distributions.

**Exercises to try:**
- Rank teams by xG per shot (conversion quality).
- Find the teams that most over- and under-performed their xG.
- Repeat the calibration table for 2019/20.

---

## Module 6 — Building and judging a prediction model (Lesson 6)

**Question:** how do you predict a match, and how do you know if your model is any good?

**Concepts:** the Poisson match model (attack/defence ratings), maximum-likelihood
fitting, the Dixon-Coles adjustment, 1X2 probabilities, log-loss, Brier score,
calibration, overfitting, benchmarks.

**Run:** `python -m football_stats.examples.06_poisson_match_prediction`

**What you learn:**
- Model: `λ_home = exp(μ + home_adv + attack_home − defence_away)`, and similarly for
  away. Fitting by maximum likelihood reproduces the observed goal totals exactly.
- From two Poisson distributions you get a full score matrix, then 1X2, over/under and
  the most likely scoreline.
- **Evaluation is everything.** On the held-out second half of 2018/19:

  | model | test log-loss |
  |-------|---------------|
  | naive baseline | 1.0353 |
  | Poisson (rho = 0) | **0.9411** |
  | Poisson (rho fitted on train) | 0.9568 |
  | bookmaker odds | 0.9169 |

- Fitting the Dixon-Coles `rho` improved the *training* likelihood but made the *test*
  log-loss worse. That is overfitting, seen with your own eyes.
- The bookmaker is still ahead — it uses team news, injuries and far more data. Beating
  the market is genuinely hard.

**Exercises to try:**
- Add a "recent form" feature (e.g. points from the last 5 matches).
- Evaluate over/under 2.5 goals instead of 1X2.
- Try a bivariate Poisson for low-scoring games.

---

## Module 7 — Elo ratings (Lesson 7)

**Question:** can a simple rating system compete with a statistical model?

**Concepts:** Elo ratings, expected score, K-factor, home advantage, goal-difference
multipliers, rating drift.

**Run:** `python -m football_stats.examples.07_elo_ratings`

**What you learn:**
- `E = 1 / (1 + 10^(-(R_home − R_away)/400))`, then
  `R_new = R_old + K × (actual − expected)`.
- Elo needs no distributional assumptions and updates after every match.
- The final Elo ordering correlates with the real league table at **r = 0.982** —
  without ever being told the points system.
- Carried into 2019/20, Elo gives a home-win Brier score of 0.25.

**Exercises to try:**
- Tune K and the home-advantage term to minimise the Brier score.
- Add a goal-difference multiplier and measure the improvement.
- Print a team's Elo history month by month.

---

## Module 8 — Cross-season prediction and simulation (Lesson 8)

**Question:** does a model survive a change of season, and how do we turn match
probabilities into title probabilities?

**Concepts:** training vs testing, out-of-sample degradation, Monte-Carlo simulation,
promoted-team priors, the difference between a forecast and a single result.

**Run:** `python -m football_stats.examples.08_predicting_a_new_season`

**What you learn:**
- A model fitted on 2018/19 gets log-loss 0.999 on 2019/20, vs 1.065 for the naive
  baseline. It still works, but it degrades — team strength changes between seasons.
- Promoted teams (Aston Villa, Norwich City, Sheffield United) have no history; the
  model treats them as league average. In practice you blend in a second-division prior.
- Monte-Carlo simulation: sample every match from the model, build the table, repeat
  2,000 times. The 2018/19 ratings made Manchester City 56% and Liverpool 44% title
  favourites for 2019/20 — Liverpool won. One season is one draw from the distribution;
  a 44% chance not happening is not a model failure.

**Exercises to try:**
- Fit on 2019/20 and back-test on 2018/19.
- Estimate each team's probability of a top-4 finish.
- Add a simple promotion/relegation prior and see how the simulation changes.

---

## Capstone project ideas

Pick one and write it up as a short report (a few charts/tables and a conclusion):

1. **Nigerian Premier Football League (NPFL) analysis.** Find or collect NPFL results,
   load them with `d.load_csv`, and reproduce Lessons 1–3. Is home advantage larger or
   smaller than in England? (Longer travel and pitch conditions often make it bigger.)
2. **Build a betting model.** Use the Poisson model to find value against the bookmaker
   odds in 2019/20. Measure your "profit" with a fixed stake. What goes wrong?
3. **Player-level expected goals.** Use a public shot dataset (e.g. from
   `statsbomb/open-data` on GitHub) to compute xG per player and season.
4. **World Cup prediction.** Collect results, fit a model, simulate a tournament and
   compare your probabilities with the bookmakers.
5. **Test a new feature.** Try rest days, travel distance, manager changes or weather.
   Does it improve held-out log-loss? (Most do not — that is a useful finding.)

## Where to go next

**Books and articles**
- *The Expected Goals Philosophy* — James Tippett (the best popular introduction).
- *Soccermatics* — David Sumpter (maths of football, very readable).
- Dixon & Coles (1997), "Modelling Association Football Scores and Inefficiencies in
  the Football Betting Market" — the original academic paper behind Lesson 6.
- Mark Taylor's "The Expected Goals philosophy" and the Opta/StatsBomb xG explainers.

**Data sources (free)**
- `github.com/jokecamp/FootballData` — the source of the bundled datasets.
- `github.com/openfootball/football.json` — results for many leagues and seasons.
- `github.com/statsbomb/open-data` — event data with xG for major competitions.
- `football-data.co.uk` — results and odds for many leagues (the original source of
  the 2019/20 dataset).
- The `worldfootballR` R package documentation keeps a good curated list of football
  data APIs and mirrors.

**Tools to learn after this course**
- `pandas` for data wrangling, `matplotlib`/`seaborn` for plotting, `scipy`/`statsmodels`
  for statistics, `scikit-learn` for machine learning. Everything in this course maps
  directly onto those libraries — you will recognise every concept.
- `understat` and `FBref` for xG and player data.

**Key terms glossary**

| Term | Plain English |
|------|---------------|
| xG (expected goals) | The probability a shot becomes a goal, summed over all shots |
| Poisson distribution | A distribution for counts (like goals) with one rate parameter |
| Lambda (λ) | The expected number of events (goals) in a match |
| p-value | How surprising the data would be if there were no real effect |
| Confidence interval | A range of plausible values for a quantity |
| Bootstrap | Resampling your data to estimate uncertainty |
| R-squared | The share of variation a model explains (0–1) |
| Log-loss | A scoring rule for probabilistic forecasts (lower = better) |
| Calibration | Whether predicted probabilities match observed frequencies |
| Overfitting | Fitting the noise in your sample, so the model fails on new data |
| Elo | A rating system that updates after each result |
| Monte-Carlo simulation | Repeating a random process many times to estimate probabilities |

---

## The one-sentence version

Football statistics is the discipline of turning counts (goals, shots, xG) into
probabilities, and then honestly measuring whether those probabilities were right.
