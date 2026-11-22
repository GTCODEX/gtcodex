"""
Lesson 6 — Predicting matches: the Poisson model vs the bookmakers

Run from the repository root:

    python -m football_stats.examples.06_poisson_match_prediction

You will learn: how to fit a Poisson match model, how to turn it into 1X2
probabilities, and how to judge a forecasting model honestly with log-loss and
Brier score — against a naive baseline AND against the betting market.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import models as m
from football_stats import stats as st


def implied_probs(odds_home: float, odds_draw: float, odds_away: float) -> tuple[float, float, float]:
    """Convert decimal odds to probabilities by removing the bookmaker's overround."""
    raw = [1 / odds_home, 1 / odds_draw, 1 / odds_away]
    overround = sum(raw)
    return tuple(p / overround for p in raw)  # type: ignore[return-value]


def evaluate_1x2(prob_sets, matches) -> dict:
    """Mean log-loss over the three outcomes for a list of (ph, pd, pa) triples."""
    losses = []
    for (ph, pd, pa), m in zip(prob_sets, matches):
        p = {"H": ph, "D": pd, "A": pa}[m.result]
        losses.append(-math.log(max(p, 1e-15)))
    return {"log_loss": st.mean(losses), "n": len(losses)}


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    train, test = d.split_by_date(matches, 0.5)
    print("=" * 72)
    print("LESSON 6  |  POISSON MATCH PREDICTION AND MODEL EVALUATION")
    print("=" * 72)
    print(f"\ntrain: first {len(train)} matches   test: last {len(test)} matches")

    model = m.fit_poisson(train)
    plain = m.fit_poisson(train, fit_rho=False)
    baseline = m.fit_baseline(train)

    print("\n--- 1. What the model learned ---------------------------------------")
    print(f"  baseline goal rate (mu)      = {math.exp(model.mu):.3f} per team per match")
    print(f"  home advantage              = {math.exp(model.home_advantage):.3f}x")
    print(f"  Dixon-Coles rho             = {model.rho:.3f}")
    print("  (rho adjusts the four lowest-scoring scorelines; see step 3 for why")
    print("   fitting it on a small sample can hurt.)")
    top_attack = model.ratings_table()[0]
    best_def = model.best_defence()
    print(f"  strongest attack            : {top_attack['team']} "
          f"({top_attack['goal_rate']:.2f} goals/match)")
    print(f"  strongest defence           : {best_def} "
          f"({math.exp(model.mu - model.defence[best_def]):.2f} conceded/match)")

    print("\n--- 2. A worked prediction ------------------------------------------")
    fixture = ("Manchester City", "Liverpool")
    p = model.match_probabilities(*fixture)
    print(f"  {fixture[0]} vs {fixture[1]}")
    print(f"    expected goals   : {p['expected_home_goals']:.2f} - {p['expected_away_goals']:.2f}")
    print(f"    1X2              : {p['home_win']:.1%} / {p['draw']:.1%} / {p['away_win']:.1%}")
    print(f"    over 2.5         : {p['over_2_5']:.1%}")
    print(f"    most likely score: {p['most_likely_score']} ({p['most_likely_prob']:.1%})")

    print("\n--- 3. How good is the model? (test set) ----------------------------")
    model_probs = [model.match_probabilities(x.home, x.away) for x in test]
    plain_probs = [plain.match_probabilities(x.home, x.away) for x in test]
    base_probs = [baseline.match_probabilities(x.home, x.away) for x in test]
    book_probs = [implied_probs(x.stat("home_odds"), x.stat("draw_odds"), x.stat("away_odds"))
                  for x in test]

    rows = [
        ("Naive baseline (league average)",
         [(b["home_win"], b["draw"], b["away_win"]) for b in base_probs]),
        ("Poisson, rho = 0",
         [(p["home_win"], p["draw"], p["away_win"]) for p in plain_probs]),
        ("Poisson, rho fitted on train",
         [(p["home_win"], p["draw"], p["away_win"]) for p in model_probs]),
        ("Bookmaker odds", book_probs),
    ]
    print(f"  {'model':<34}{'train LL':>10}{'test log-loss':>15}")
    for name, probs in rows:
        if name == "Bookmaker odds":
            print(f"  {name:<34}{'—':>10}{evaluate_1x2(probs, test)['log_loss']:>15.4f}")
        else:
            obj = {"Naive baseline (league average)": baseline,
                   "Poisson, rho = 0": plain,
                   "Poisson, rho fitted on train": model}[name]
            train_ll = obj.log_likelihood(train) if hasattr(obj, "log_likelihood") else float("nan")
            print(f"  {name:<34}{train_ll:>10.2f}{evaluate_1x2(probs, test)['log_loss']:>15.4f}")
    print("\n  Lower log-loss is better. The Poisson model beats the naive baseline,")
    print("  but the bookmaker — which uses team news, injuries and far more data —")
    print("  is still ahead. Note how fitting rho improves the TRAIN likelihood yet")
    print("  worsens the TEST log-loss: a textbook case of overfitting a small sample.")

    print("\n--- 4. Are the probabilities calibrated? ---------------------------")
    # Bin predictions by home-win probability and compare with observed frequency.
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    print(f"  {'predicted':<14}{'n':>5}{'mean pred':>11}{'observed':>10}")
    for lo, hi in bins:
        idx = [i for i, p in enumerate(model_probs) if lo <= p["home_win"] < hi]
        if not idx:
            continue
        mean_pred = st.mean([model_probs[i]["home_win"] for i in idx])
        observed = st.mean([1 if test[i].result == "H" else 0 for i in idx])
        print(f"  {f'{lo:.1f}-{hi:.1f}':<14}{len(idx):>5}{mean_pred:>11.2f}{observed:>10.2f}")

    print("\n--- 5. Your turn ----------------------------------------------------")
    print("* Add a 'recent form' feature and see if log-loss improves.")
    print("* Try a larger rho range or a bivariate Poisson for low-scoring games.")
    print("* Evaluate over/under 2.5 goals instead of 1X2.")


if __name__ == "__main__":
    main()
