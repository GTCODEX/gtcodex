"""
Lesson 8 — Putting it together: predict a new season and simulate it

Run from the repository root:

    python -m football_stats.examples.08_predicting_a_new_season

You will learn: how to train on one season and test on the next (the honest test of
a model), how Monte-Carlo simulation turns match probabilities into title and
relegation probabilities, and why the best model is not always the most complex one.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import models as m
from football_stats import stats as st


def main() -> None:
    train = d.load_dataset("epl_2018_19")
    test = d.load_dataset("epl_2019_20")

    print("=" * 72)
    print("LESSON 8  |  FROM ONE SEASON TO THE NEXT, AND SEASON SIMULATION")
    print("=" * 72)
    print(f"\ntrain: 2018/19 ({len(train)} matches)   test: 2019/20 ({len(test)} matches)")

    model = m.fit_poisson(train)
    baseline = m.fit_baseline(train)

    print("\n--- 1. Does the model survive a season change? ---------------------")
    print(f"  {'model':<30}{'log-loss on 2019/20':>24}")
    for name, predict in (
        ("Naive baseline", lambda x: baseline.match_probabilities(x.home, x.away)),
        ("Poisson (fitted on 2018/19)", lambda x: model.match_probabilities(x.home, x.away)),
    ):
        probs = [predict(x) for x in test]
        losses = [-math.log(max({"H": p["home_win"], "D": p["draw"], "A": p["away_win"]}[x.result], 1e-15))
                  for p, x in zip(probs, test)]
        print(f"  {name:<30}{st.mean(losses):>24.4f}")
    print("  Team strength changes between seasons (transfers, managers), so a model")
    print("  trained on one season usually degrades a little on the next. That is")
    print("  expected — and it is why clubs re-fit models continuously.")
    promoted = sorted(set(d.team_names(test)) - set(d.team_names(train)))
    print(f"\n  Promoted teams with no 2018/19 history: {', '.join(promoted)}.")
    print("  The model treats them as league-average (unseen_rating = 0.0); in")
    print("  practice you would blend in a prior from the second division.")
    print("  (The full predictor, football_stats.predictor, rates them like the weakest")
    print("  40% of last season's teams instead — see PredictorConfig.promoted_prior.)")

    print("\n--- 2. Monte-Carlo simulation of a season --------------------------")
    teams = d.team_names(test)
    sim = m.simulate_season(model, teams, n_sim=2000, seed=7)
    print(f"  {sim['n_sim']} simulated 2019/20 seasons using the 2018/19 ratings:\n")
    print(f"  {'team':<24}{'title %':>9}{'avg pts':>9}{'avg pos':>9}")
    ranked = sorted(teams, key=lambda t: -sim["title_prob"][t])
    for t in ranked[:8]:
        print(f"  {t:<24}{sim['title_prob'][t]:>8.1%}{sim['avg_points'][t]:>9.1f}"
              f"{sim['avg_position'][t]:>9.1f}")

    print("\n  The simulation samples each match from the Poisson model, builds the")
    print("  table, and repeats. Title probabilities emerge from the distribution,")
    print("  not from a single 'most likely' table.")

    print("\n--- 3. Compare simulation with reality -----------------------------")
    actual = d.league_table(test)
    print(f"  actual 2019/20 champion: {actual[0]['team']}")
    print(f"  simulated title odds   : {ranked[0]} ({sim['title_prob'][ranked[0]]:.1%})")
    print("  A single season is one draw from the distribution — one result can")
    print("  differ from the forecast without the model being wrong.")

    print("\n--- 4. Your turn ----------------------------------------------------")
    print("* Simulate with a model fitted on 2019/20 and back-test on 2018/19.")
    print("* Add promotion/relegation by mixing ratings across divisions.")
    print("* Estimate the probability of each team finishing in the top 4.")


if __name__ == "__main__":
    main()
