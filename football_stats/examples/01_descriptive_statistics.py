"""
Lesson 1 — Descriptive statistics: what does a football season look like?

Run from the repository root:

    python -m football_stats.examples.01_descriptive_statistics

You will learn: mean, median, spread, percentiles, histograms, and why the distribution
of football goals is skewed (most games have few goals, a few have many).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running both as `python -m ...` and as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import stats as st


def bar(count: int, scale: float = 1.0, width: int = 40) -> str:
    n = int(round(count * scale))
    return "#" * min(n, width)


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    home_goals = [m.home_goals for m in matches]
    away_goals = [m.away_goals for m in matches]
    total_goals = [m.total_goals for m in matches]

    print("=" * 72)
    print("LESSON 1  |  DESCRIPTIVE STATISTICS OF THE 2018/19 PREMIER LEAGUE")
    print("=" * 72)
    print(f"matches: {len(matches)}   teams: {len(d.team_names(matches))}")

    print("\n--- 1. Goals per team per match -------------------------------------")
    for label, xs in (("home", home_goals), ("away", away_goals), ("total", total_goals)):
        s = st.summary(xs)
        print(f"{label:>5}: mean {s['mean']:.2f}  median {s['median']:.1f}  "
              f"sd {s['stdev']:.2f}  min {s['min']}  max {s['max']}  "
              f"p10 {s['p10']:.0f}  p90 {s['p90']:.0f}")

    print("\n--- 2. The shape of the distribution (total goals) ------------------")
    print("The distribution is concentrated at 1-3 goals with a long right tail:")
    print("most matches are low-scoring, and a handful of 5-0s and 6-1s stretch it out.")
    counts = {k: total_goals.count(k) for k in range(0, 8)}
    scale = 40 / max(counts.values())
    for goals, n in counts.items():
        print(f"  {goals} goals: {bar(n, scale)} {n}")

    print("\n--- 3. Team-level variation -----------------------------------------")
    print("Some teams score far more than others. Here are the extremes:")
    table = d.league_table(matches)
    print(f"  most goals   : {table[0]['team']} ({table[0]['gf']})")
    print(f"  fewest goals : {table[-1]['team']} ({table[-1]['gf']})")

    print("\n--- 4. Home vs away -------------------------------------------------")
    ha = d.home_advantage(matches)
    print(f"  home goals per game : {ha['home_goals_per_game']:.2f}")
    print(f"  away goals per game : {ha['away_goals_per_game']:.2f}")
    print(f"  home wins {ha['home_win_pct']:.1%}  draws {ha['draw_pct']:.1%}  "
          f"away wins {ha['away_win_pct']:.1%}")

    print("\n--- 5. League table (top 6) -----------------------------------------")
    print(f"  {'team':<24}{'p':>3}{'w':>4}{'d':>4}{'l':>4}{'gf':>5}{'ga':>5}{'gd':>5}{'pts':>5}")
    for r in table[:6]:
        print(f"  {r['team']:<24}{r['p']:>3}{r['w']:>4}{r['d']:>4}{r['l']:>4}"
              f"{r['gf']:>5}{r['ga']:>5}{r['gd']:>5}{r['pts']:>5}")

    print("\n--- 6. Your turn ----------------------------------------------------")
    print("* What is the interquartile range (p75 - p25) of total goals?")
    print("* Which is larger: the spread of home goals or away goals?")
    print("* Compute the same summary for the 2019/20 season and compare.")


if __name__ == "__main__":
    main()
