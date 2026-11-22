"""
Lesson 7 — Elo ratings: a simple, powerful alternative to Poisson models

Run from the repository root:

    python -m football_stats.examples.07_elo_ratings

You will learn: how Elo ratings work, why they update multiplicatively, how to
incorporate home advantage and goal difference, and how to compare two rating
systems against the final league table.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import models as m
from football_stats import stats as st


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    elo = m.Elo(k=20, home_advantage=100).fit(matches)
    table = d.league_table(matches)

    print("=" * 72)
    print("LESSON 7  |  ELO RATINGS")
    print("=" * 72)

    print("\n--- 1. How Elo works ------------------------------------------------")
    print("  Every team starts at 1500. Before each match we predict the home team's")
    print("  expected score E = 1 / (1 + 10^(-(Rh - Ra)/400)).")
    print("  After the match: R_new = R_old + K * (actual - expected).")
    print("  Winning when expected loses you more points; the update is self-correcting.")

    print("\n--- 2. Final Elo table vs the real table ---------------------------")
    elo_table = elo.table()
    actual = {r["team"]: r for r in table}
    print(f"  {'rank':<6}{'team':<24}{'elo':>8}{'pts':>6}{'gd':>6}")
    for i, r in enumerate(elo_table[:8]):
        a = actual[r["team"]]
        print(f"  {i + 1:<6}{r['team']:<24}{r['rating']:>8.0f}{a['pts']:>6}{a['gd']:>6}")

    elo_rank = [r["team"] for r in elo_table]
    actual_rank = [r["team"] for r in table]
    # Spearman correlation between the two rankings
    elo_pos = [elo_rank.index(t) for t in actual_rank]
    actual_pos = list(range(len(actual_rank)))
    rho = st.pearson(elo_pos, actual_pos)
    print(f"\n  Rank correlation with the final table: r = {rho:.3f}")
    print("  (1.0 = identical ordering.) Elo tracks the table closely without ever")
    print("  being told the points system — it only sees goals and results.")

    print("\n--- 3. Predicting with Elo -------------------------------------------")
    # Carry ratings into 2019/20 and see how well they predict the new season.
    next_season = d.load_dataset("epl_2019_20")
    correct = 0
    probs = []
    outcomes = []
    for match in next_season:
        e = elo.expected(match.home, match.away)
        pred = "H" if e > 0.55 else ("A" if e < 0.45 else "D")
        correct += pred == match.result
        probs.append(e)
        outcomes.append(1 if match.result == "H" else 0)
        elo.update(match)
    print(f"  2019/20 home-win probability: Brier = {st.brier_score(probs, outcomes):.4f}")
    print(f"  naive 1X2 accuracy (thresholds 0.55/0.45): {correct / len(next_season):.1%}")
    print("  Compare with Lesson 6's Poisson log-loss for a like-for-like check.")

    print("\n--- 4. Your turn ----------------------------------------------------")
    print("* Tune K and the home-advantage term to minimise the Brier score.")
    print("* Add a goal-difference multiplier and see if it helps.")
    print("* Plot Elo history for one team across the season (print a table per month).")


if __name__ == "__main__":
    main()
