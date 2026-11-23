"""
Lesson 10 — Writing forecasts down before you score them

Run from the repository root:

    python -m football_stats.examples.10_forecast_log

A backtest measures a *model*. It cannot tell you whether the forecasts you
actually made were any good, because it never had to commit to one before the
match. This lesson keeps a running log: every forecast is written down with a
timestamp, then settled against the real result once the match is played.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from football_stats import data as d
from football_stats import prediction_log as plog
from football_stats import predictor as p


def main() -> None:
    print("=" * 72)
    print("LESSON 10  |  THE FORECAST LOG")
    print("=" * 72)

    # Work on a throwaway log so the lesson does not touch your real one.
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "prediction_log.json"

        print("\n--- 1. Fit on the recent seasons ----------------------------------")
        predictor = p.fit_predictor(d.load_dataset("epl_recent"),
                                    config=p.PredictorConfig(holdout_frac=0.0),
                                    verbose=True)

        print("\n--- 2. Commit to a forecast ---------------------------------------")
        fixtures = [("Liverpool", "Manchester United"),
                    ("Hull City", "Brighton & Hove Albion")]
        for home, away in fixtures:
            pred = predictor.predict(home, away)
            rec = plog.record(pred, fixture_date="2026-11-22",
                              dataset="epl_recent", path=log_path)
            print(f"  {home} v {away}: {pred.most_likely_outcome} at "
                  f"{pred.confidence:.1%}  ->  logged as {rec.id} "
                  f"({rec.status})")

        print("\n  Before the match the log can only say 'pending':")
        for line in plog.table(plog.load_log(log_path)).splitlines()[1:]:
            print("    " + line)

        print("\n--- 3. Settle it once the results exist ---------------------------")
        n = plog.settle_from_datasets(dataset_ids=["epl_2026_27"], path=log_path,
                                      verbose=False)
        print(f"  settled {n} record(s) from epl_2026_27")

        print("\n--- 4. The scorecard ----------------------------------------------")
        print(plog.summary(plog.load_log(log_path)))

        print("\n--- 5. Your turn ---------------------------------------------------")
        print("* Log a real forecast: python -m football_stats.predict \\")
        print('      "Arsenal" "Chelsea" --dataset epl_recent --date 2026-11-29 --log')
        print("* Then settle and score it:")
        print("      python -m football_stats.prediction_log --settle")
        print("      python -m football_stats.prediction_log")
        print("* Or open the dashboard's Forecast log tab and press 'Settle results'.")
        print("* Two picks prove nothing. Ten is a hint; a hundred is a measurement.")

    print(f"\nYour real log is at {plog.DEFAULT_LOG_PATH}")
    real = plog.load_log()
    if real:
        print(plog.summary(real))


if __name__ == "__main__":
    main()
