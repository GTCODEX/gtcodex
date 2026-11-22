"""
Lesson 9 — Predicting match outcomes with the ensemble predictor

Run from the repository root:

    python -m football_stats.examples.09_outcome_predictor

The predictor blends three signals — a Poisson model, Elo ratings and the betting
market — tunes the blend weights on held-out data, and calibrates the final
probabilities. This lesson shows how to use it and, more importantly, how to measure
whether it is actually accurate.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import predictor as p


def main() -> None:
    train = d.load_dataset("epl_2018_19")

    print("=" * 72)
    print("LESSON 9  |  PREDICTING MATCH OUTCOMES")
    print("=" * 72)

    print("\n--- 1. Fit the predictor -------------------------------------------")
    predictor = p.fit_predictor(train, verbose=True)
    print(f"  training matches: {predictor.n_train}")
    print(f"  blend weights: poisson {predictor.config.poisson_weight:.2f}, "
          f"elo {predictor.config.elo_weight:.2f}, "
          f"odds {predictor.config.odds_weight:.2f}")
    print(f"  calibration temperature: {predictor.temperature:.2f}")

    print("\n--- 2. Predict a fixture ------------------------------------------")
    print(predictor.predict("Arsenal", "Chelsea").summary())
    print()
    print(predictor.predict("Arsenal", "Chelsea", odds=(2.10, 3.40, 3.60)).summary())

    print("\n--- 3. How accurate is it? (walk-forward backtest) -----------------")
    report = p.backtest(train, min_train=190, step=10, verbose=True)

    print("\n--- 4. Compare with the betting market ----------------------------")
    vs = report["vs_market"]
    print(f"  on {vs['n']} matches with odds:")
    print(f"    model  log-loss {vs['model_log_loss']:.4f}")
    print(f"    market log-loss {vs['market_log_loss']:.4f}")
    gap = vs["model_log_loss"] - vs["market_log_loss"]
    print(f"  the market is ahead by {gap:.4f} — that gap is the cost of not having")
    print("  team news, injuries, and the bookmaker's own modelling team.")

    print("\n--- 5. Calibration -------------------------------------------------")
    print("  A well-calibrated model predicts 60% when the event happens 60% of the time.")
    for row in report["calibration"]:
        if row["n"]:
            print(f"    predicted {row['bin'][0]:.1f}-{row['bin'][1]:.1f}  n={row['n']:<4}"
                  f" mean {row['mean_pred']:.2f}  observed {row['observed']:.2f}")

    print("\n--- 6. Your turn ---------------------------------------------------")
    print("* Tune --decay and --ridge with the CLI: python -m football_stats.predict --backtest --decay 0.98")
    print("* Predict a full season: python -m football_stats.predict --season epl_2019_20 --train epl_2018_19")
    print("* Add a fourth signal (e.g. recent form) and see if log-loss improves.")


if __name__ == "__main__":
    main()
