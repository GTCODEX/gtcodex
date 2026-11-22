"""
Lesson 5 — Expected goals (xG): the most important number in modern football

Run from the repository root:

    python -m football_stats.examples.05_expected_goals

You will learn: what xG measures, why it predicts the future better than goals,
how to check a model with calibration, and how to build a Poisson model from xG.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import stats as st


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    xg = [m.stat("home_xg") + m.stat("away_xg") for m in matches]
    goals = [m.total_goals for m in matches]

    print("=" * 72)
    print("LESSON 5  |  EXPECTED GOALS (xG)")
    print("=" * 72)

    print("\n--- 1. xG and goals measure different things -----------------------")
    print(f"  mean xG per match     = {st.mean(xg):.2f}")
    print(f"  mean goals per match  = {st.mean(goals):.2f}")
    print(f"  correlation           = {st.pearson(xg, goals):.3f}")
    print("  They agree on average, but not match by match: a team can out-score its")
    print("  xG by luck in the short run. The signal is in the underlying rate.")

    print("\n--- 2. Does xG predict FUTURE goals better than past goals? ---------")
    # Split the season in half and see which first-half statistic predicts the second.
    train, test = d.split_by_date(matches, 0.5)
    print(f"  first half: {len(train)} matches, second half: {len(test)} matches")

    def first_half_rate(ms, team, kind):
        """Per-team scoring rate from the first half, on the chosen measure."""
        total, played = 0.0, 0
        for m in ms:
            if m.home == team:
                total += {"goals": m.home_goals, "xG": m.stat("home_xg"),
                          "shots on target": m.stat("home_shots_on_target")}[kind]
                played += 1
            elif m.away == team:
                total += {"goals": m.away_goals, "xG": m.stat("away_xg"),
                          "shots on target": m.stat("away_shots_on_target")}[kind]
                played += 1
        return total / played  # per-match rate

    # Each measure lives on its own scale (goals 0-6, shots on target 0-10), so we
    # rescale it to the goals scale using the league base rate before comparing.
    league_goals = st.mean([m.total_goals for m in train]) / 2  # per team per match
    league_measure = {
        "goals": 1.0,
        "xG": st.mean([m.stat("home_xg") for m in train]),
        "shots on target": st.mean([m.stat("home_shots_on_target") for m in train]),
    }
    scale = {k: league_goals / v for k, v in league_measure.items()}

    print(f"  {'first-half measure':<22}{'MAE vs second-half goals':>26}")
    for kind in ("goals", "xG", "shots on target"):
        errors = []
        for m in test:
            for team, is_home in ((m.home, True), (m.away, False)):
                rate = first_half_rate(train, team, kind) * scale[kind]
                actual = m.home_goals if is_home else m.away_goals
                errors.append(actual - rate)
        print(f"  {kind:<22}{st.mae([0] * len(errors), errors):>26.3f} goals")

    print("\n  All three are close, which is the honest finding: over half a season the")
    print("  differences between chance measures are small. xG is designed to be the")
    print("  most stable, but a single season is too short to prove it definitively.")

    print("\n--- 3. Calibration: do the probabilities mean what they say? -------")
    # Group matches by total xG and compare with actual goals.
    bins = [(0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 3.5), (3.5, 10)]
    print(f"  {'xG range':<12}{'matches':>9}{'mean xG':>10}{'mean goals':>12}")
    for lo, hi in bins:
        idx = [i for i, x in enumerate(xg) if lo <= x < hi]
        if not idx:
            continue
        print(f"  {f'{lo}-{hi}':<12}{len(idx):>9}"
              f"{st.mean([xg[i] for i in idx]):>10.2f}"
              f"{st.mean([goals[i] for i in idx]):>12.2f}")
    print("  Close agreement means the xG model is well calibrated.")

    print("\n--- 4. Build a Poisson model straight from xG -----------------------")
    print("  If we trust xG, we can price a match with two Poisson distributions.")
    print("  Example: a match with home xG 1.8 and away xG 1.1")
    lh, la = 1.8, 1.1
    ph = pd = pa = 0.0
    for i in range(11):
        for j in range(11):
            p = st.poisson_pmf(i, lh) * st.poisson_pmf(j, la)
            if i > j:
                ph += p
            elif i == j:
                pd += p
            else:
                pa += p
    print(f"  P(home win) = {ph:.1%}   P(draw) = {pd:.1%}   P(away win) = {pa:.1%}")
    print(f"  P(over 2.5) = {1 - st.poisson_cdf(2, lh + la):.1%}")

    print("\n--- 5. Your turn ----------------------------------------------------")
    print("* Compute xG per shot for each team and rank them (conversion quality).")
    print("* Find the teams that most over- and under-performed their xG.")
    print("* Repeat the calibration table for the 2019/20 season.")


if __name__ == "__main__":
    main()
