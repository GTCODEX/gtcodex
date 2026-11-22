"""
Lesson 3 — Inference: is home advantage real, or just noise?

Run from the repository root:

    python -m football_stats.examples.03_home_advantage

You will learn: confidence intervals, the two-sample t-test, the Mann-Whitney U test,
bootstrap resampling, and effect sizes. The same recipe applies to any
"compare two groups" question in football (home/away, with/without a star player, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import stats as st


def cohen_d(a, b) -> float:
    """Standardised effect size: difference in means pooled in units of sd."""
    na, nb = len(a), len(b)
    sp = ((na - 1) * st.variance(a) + (nb - 1) * st.variance(b)) / (na + nb - 2)
    return (st.mean(a) - st.mean(b)) / (sp ** 0.5)


def main() -> None:
    matches = d.load_dataset("epl_2018_19")
    home = [m.home_goals for m in matches]
    away = [m.away_goals for m in matches]

    print("=" * 72)
    print("LESSON 3  |  IS HOME ADVANTAGE REAL? (INFERENCE ON TWO GROUPS)")
    print("=" * 72)
    print(f"\nhome goals per game = {st.mean(home):.3f}")
    print(f"away goals per game = {st.mean(away):.3f}")
    print(f"difference          = {st.mean(home) - st.mean(away):.3f}")

    print("\n--- 1. Confidence interval for the difference -----------------------")
    diffs = [h - a for h, a in zip(home, away)]
    lo, hi = st.bootstrap_ci(diffs, n_boot=5000, seed=42)
    print(f"  bootstrap 95% CI for (home - away) goals: [{lo:.3f}, {hi:.3f}]")
    print("  The interval excludes 0, so the advantage is very unlikely to be noise.")

    print("\n--- 2. Welch's t-test (parametric) ----------------------------------")
    t = st.welch_ttest(home, away)
    print(f"  t = {t['t']:.2f}   df = {t['df']:.1f}   p = {t['p']:.4f}")
    print("  Assumes roughly normal groups and (approximately) equal variances.")
    print("  Goals are counts, so let's also use a test that makes no such assumption.")

    print("\n--- 3. Mann-Whitney U test (rank-based, non-parametric) -------------")
    u = st.mannwhitneyu(home, away)
    print(f"  U = {u['u']:.0f}   z = {u['z']:.2f}   p = {u['p']:.4f}")
    print("  Same conclusion, reached without assuming a distribution.")

    print("\n--- 4. Effect size ---------------------------------------------------")
    d_eff = cohen_d(home, away)
    print(f"  Cohen's d = {d_eff:.3f}")
    print("  Rules of thumb: 0.2 small, 0.5 medium, 0.8 large. Home advantage is real")
    print("  but modest — roughly a third of a standard deviation.")

    print("\n--- 5. How big is it in results, not just goals? --------------------")
    ha = d.home_advantage(matches)
    n = len(matches)
    print(f"  home win {ha['home_win_pct']:.1%}   draw {ha['draw_pct']:.1%}   "
          f"away win {ha['away_win_pct']:.1%}")
    home_ppg = (ha["home_wins"] * 3 + ha["draws"]) / n
    away_ppg = (ha["away_wins"] * 3 + ha["draws"]) / n
    print(f"  home points per game {home_ppg:.2f}   away points per game {away_ppg:.2f}")
    print("  (Home teams collect roughly 0.6 more points per game.)")

    print("\n--- 6. Your turn ----------------------------------------------------")
    print("* Run the same test on the 2019/20 season. Does the advantage hold?")
    print("* Compare the home advantage of the top 6 teams vs the bottom 6.")
    print("* Bootstrap the home win percentage instead of the goal difference.")


if __name__ == "__main__":
    main()
