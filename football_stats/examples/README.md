# Tutorial scripts

Eight runnable lessons. Each prints a report, explains the ideas, and ends with
exercises. See [../CURRICULUM.md](../CURRICULUM.md) for the full course.

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

| Script | Topic | Key functions |
|--------|-------|---------------|
| `01_descriptive_statistics.py` | describing a season | `stats.summary`, `stats.histogram`, `data.league_table` |
| `02_poisson_distribution.py` | modelling goal counts | `stats.poisson_pmf`, `stats.fit_poisson`, `stats.chi_square_gof` |
| `03_home_advantage.py` | inference on two groups | `stats.welch_ttest`, `stats.mannwhitneyu`, `stats.bootstrap_ci` |
| `04_correlation_regression.py` | what predicts goals | `stats.pearson`, `stats.linregress`, `stats.linear_regression`, `stats.logistic_regression` |
| `05_expected_goals.py` | xG and calibration | out-of-sample MAE, calibration tables |
| `06_poisson_match_prediction.py` | match models & evaluation | `models.fit_poisson`, log-loss vs the bookmaker |
| `07_elo_ratings.py` | rating systems | `models.Elo` |
| `08_predicting_a_new_season.py` | cross-season + simulation | `models.simulate_season` |

## Tips

- Run them in order; later lessons reuse ideas from earlier ones.
- Change a number and re-run. That is the fastest way to build intuition.
- Every script ends with **"Your turn"** exercises — do them before moving on.
- To use your own data, call `data.load_csv("your_file.csv")` with the same column
  layout (extra columns are kept automatically).
