"""
Lesson 2 — Probability distributions: modelling goals with the Poisson distribution

Run from the repository root:

    python -m football_stats.examples.02_poisson_distribution

You will learn: the Poisson distribution, why it is the natural first model for goals,
how to fit it (lambda = mean), and how to test it with a chi-square goodness-of-fit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import stats as st


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    total_goals = [m.total_goals for m in matches]

    print("=" * 72)
    print("LESSON 2  |  MODELLING GOALS WITH THE POISSON DISTRIBUTION")
    print("=" * 72)

    lam = st.fit_poisson(total_goals)
    print(f"\nTotal goals per match: mean = {lam:.3f}")
    print("The maximum-likelihood estimate of lambda is simply the sample mean.\n")

    print("--- 1. Observed vs Poisson-expected frequencies ---------------------")
    n = len(total_goals)
    # group 6+ so every expected cell is >= 5 (a chi-square requirement)
    observed = [total_goals.count(k) for k in range(0, 6)]
    observed.append(sum(total_goals.count(k) for k in range(6, 20)))
    expected = [n * st.poisson_pmf(k, lam) for k in range(0, 6)]
    expected.append(sum(n * st.poisson_pmf(k, lam) for k in range(6, 20)))
    labels = ["0", "1", "2", "3", "4", "5", "6+"]
    print(f"  {'goals':<6}{'observed':>10}{'expected':>10}{'diff':>10}")
    for lab, o, e in zip(labels, observed, expected):
        print(f"  {lab:<6}{o:>10}{e:>10.1f}{o - e:>10.1f}")

    gof = st.chi_square_gof(observed, expected)
    print(f"\n  chi-square = {gof['chi2']:.2f}  df = {gof['df']}  p = {gof['p']:.3f}")
    print("  A small p-value (say < 0.05) means the Poisson model fits poorly.")
    print(f"  Here p = {gof['p']:.2f}, so a single Poisson describes total goals well —")
    print("  the differences are within what random variation produces.")

    print("\n--- 2. From a distribution to betting-style probabilities -----------")
    print(f"  P(over 2.5 goals) = {1 - st.poisson_cdf(2, lam):.1%}")
    print(f"  P(under 2.5 goals) = {st.poisson_cdf(2, lam):.1%}")
    print(f"  P(0-0)            = {st.poisson_pmf(0, lam) * st.poisson_pmf(0, lam):.1%}"
          "   (if the two teams were independent)")
    print(f"  most likely total = {st.mode(total_goals)} goals")

    print("\n--- 3. Rate per team, not just per match ----------------------------")
    home = [m.home_goals for m in matches]
    away = [m.away_goals for m in matches]
    print(f"  home lambda = {st.mean(home):.3f}   away lambda = {st.mean(away):.3f}")
    print("  Home and away goals have different rates — so the next lesson fits a")
    print("  separate distribution to each, and Lesson 6 turns that into a match model.")

    print("\n--- 4. Your turn ----------------------------------------------------")
    print("* Fit a Poisson to home goals only and repeat the chi-square test.")
    print("* What is P(exactly 3 goals) for the away team?")
    print("* Try the negative-binomial idea: what extra parameter would fix over-dispersion?")


if __name__ == "__main__":
    main()
