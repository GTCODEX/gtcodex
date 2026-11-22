"""
Lesson 4 — Correlation and regression: what actually predicts goals?

Run from the repository root:

    python -m football_stats.examples.04_correlation_regression

You will learn: Pearson vs Spearman correlation, simple and multiple linear
regression, R-squared, and how to read a regression coefficient in context.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import stats as st


def main() -> None:
    matches = d.load_dataset("epl_2018_19")

    print("=" * 72)
    print("LESSON 4  |  CORRELATION AND REGRESSION")
    print("=" * 72)

    home_goals = [m.home_goals for m in matches]
    home_shots = [m.stat("home_shots") for m in matches]
    home_sot = [m.stat("home_shots_on_target") for m in matches]
    home_xg = [m.stat("home_xg") for m in matches]
    home_poss = [m.stat("home_possession") for m in matches]

    print("\n--- 1. Which statistic correlates most with goals? -----------------")
    pairs = [("shots", home_shots), ("shots on target", home_sot),
             ("expected goals (xG)", home_xg), ("possession %", home_poss)]
    print(f"  {'statistic':<22}{'Pearson r':>12}{'Spearman':>12}")
    for name, xs in pairs:
        print(f"  {name:<22}{st.pearson(xs, home_goals):>12.3f}"
              f"{st.spearman(xs, home_goals):>12.3f}")
    print("\n  Shots on target beat raw shots: quality matters more than quantity.")
    print("  Possession is the weakest of the four — having the ball is not scoring.")
    print("  xG sits between the two shot measures here; the real test is which one")
    print("  predicts the FUTURE, not which one best describes the same match.")

    print("\n--- 2. Simple linear regression: goals = a + b * shots -------------")
    reg = st.linregress(home_shots, home_goals)
    print(f"  goals = {reg['intercept']:.3f} + {reg['slope']:.4f} * shots")
    print(f"  r = {reg['r']:.3f}   R^2 = {reg['r2']:.3f}   p(slope) = {reg['p_slope']:.2e}")
    print(f"  Interpretation: each extra shot adds about {reg['slope']:.3f} goals,")
    print(f"  and shots explain {reg['r2']:.1%} of the variation in goals.")

    print("\n--- 3. Multiple regression: shots + possession + xG ----------------")
    X = [[s, p, x] for s, p, x in zip(home_shots, home_poss, home_xg)]
    multi = st.linear_regression(X, home_goals)
    names = ["intercept", "shots", "possession", "xG"]
    for name, b in zip(names, multi["coef"]):
        print(f"  {name:<12}{b:>10.4f}")
    print(f"  R^2 = {multi['r2']:.3f}   RMSE = {multi['rmse']:.3f}")
    print("  With xG in the model, shots and possession add almost nothing — and the")
    print("  shots coefficient even flips sign. That is multicollinearity: xG and shots")
    print("  carry the same information, so the model can trade one against the other.")

    print("\n--- 4. Logistic regression: predicting a win ------------------------")
    # Predict home win from xG difference and possession.
    Xl = [[x - m.stat("away_xg"), m.stat("home_possession") - 50]
          for x, m in zip(home_xg, matches)]
    yl = [1 if m.result == "H" else 0 for m in matches]
    logit = st.logistic_regression(Xl, yl, lr=0.05, iters=3000)
    print(f"  weights (intercept, xG diff, possession diff): "
          f"{[round(w, 4) for w in logit['weights']]}")
    probs = [st.predict_logistic(logit["weights"], x) for x in Xl]
    print(f"  Brier score = {st.brier_score(probs, yl):.4f}   "
          f"ROC-AUC = {st.roc_auc(probs, yl):.3f}")
    print("  An AUC of 0.5 is a coin flip; 0.8+ is strong. xG difference is a solid")
    print("  predictor of results — which is exactly why clubs invest in it.")

    print("\n--- 5. Your turn ----------------------------------------------------")
    print("* Regress goals on shots for away teams. Is the slope the same?")
    print("* Add a 'home advantage' dummy variable and see how much it helps.")
    print("* Compute the correlation between xG difference and the result (H/D/A).")


if __name__ == "__main__":
    main()
