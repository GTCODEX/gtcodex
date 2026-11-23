"""
Command-line match predictor.

Examples
--------
Predict one fixture (fit on the whole 2018/19 season, no odds)::

    python -m football_stats.predict "Arsenal" "Chelsea"

Predict with the bookmaker's odds included::

    python -m football_stats.predict "Arsenal" "Chelsea" --odds 2.10 3.40 3.60

Measure how accurate the predictor really is (walk-forward backtest)::

    python -m football_stats.predict --backtest
    python -m football_stats.predict --backtest --decay 0.99 --ridge 0.001

Predict a whole season using another season as the training history::

    python -m football_stats.predict --season epl_2019_20 --train epl_2018_19 --round 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from football_stats import data as d
from football_stats import predictor as p


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m football_stats.predict",
        description="Predict football match outcomes from statistical data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("home", nargs="?", help="home team, e.g. 'Arsenal'")
    ap.add_argument("away", nargs="?", help="away team, e.g. 'Chelsea'")
    ap.add_argument("--odds", nargs=3, type=float, metavar=("HOME", "DRAW", "AWAY"),
                    help="decimal 1X2 odds to blend the market signal in")
    ap.add_argument("--dataset", default="epl_2018_19",
                    help="dataset to fit on (default: epl_2018_19)")
    ap.add_argument("--backtest", action="store_true",
                    help="run a walk-forward accuracy backtest instead of predicting")
    ap.add_argument("--season", help="predict every match in this dataset")
    ap.add_argument("--train", help="dataset to fit on when using --season")
    ap.add_argument("--round", type=int,
                    help="with --season, only predict matches from this game week on")
    ap.add_argument("--decay", type=float, default=0.99,
                    help="recency weighting (default 0.99)")
    ap.add_argument("--ridge", type=float, default=0.001,
                    help="rating shrinkage (default 0.001)")
    ap.add_argument("--no-calibration", action="store_true",
                    help="skip temperature calibration")
    ap.add_argument("--date", help="fixture date (YYYY-MM-DD), stored with --log")
    ap.add_argument("--log", action="store_true",
                    help="append this forecast to data/prediction_log.json")
    ap.add_argument("--json", action="store_true", help="output JSON")
    ap.add_argument("--quiet", action="store_true", help="less progress output")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = p.PredictorConfig(decay=args.decay, ridge=args.ridge,
                            calibrate=not args.no_calibration)

    if args.backtest:
        matches = d.load_dataset(args.dataset)
        report = p.backtest(matches, config=cfg, verbose=not args.quiet)
        if args.json:
            clean = {k: v for k, v in report.items()
                     if k not in ("predictions", "matches", "calibration")}
            print(json.dumps(clean, indent=2, default=str))
        else:
            print("\nCalibration (predicted home-win prob vs observed frequency):")
            for row in report["calibration"]:
                if row["n"]:
                    print(f"  {row['bin'][0]:.1f}-{row['bin'][1]:.1f}  n={row['n']:<4}"
                          f" predicted {row['mean_pred']:.2f}  observed {row['observed']:.2f}")
            vs = report["vs_market"]
            if vs.get("n"):
                print(f"\n  vs the betting market on the same {vs['n']} matches:")
                print(f"    model log-loss   {vs['model_log_loss']:.4f}")
                print(f"    market log-loss  {vs['market_log_loss']:.4f}")
        return 0

    if args.season:
        train = d.load_dataset(args.train or args.dataset)
        season = d.load_dataset(args.season)
        if args.round:
            # a 20-team league plays 10 matches per round; --round N keeps rounds N+
            start_idx = max(0, (args.round - 1) * 10)
            season = season[start_idx:]
        predictor = p.fit_predictor(train, config=cfg, verbose=not args.quiet)
        preds = predictor.predict_many(season)
        if args.json:
            print(json.dumps([x.as_dict() for x in preds], indent=2))
        else:
            for x in preds:
                print(x.summary())
                print()
        return 0

    if not args.home or not args.away:
        _parser().error("give a home and away team, or use --backtest / --season")

    train = d.load_dataset(args.dataset)
    predictor = p.fit_predictor(train, config=cfg, verbose=not args.quiet)
    pred = predictor.predict(args.home, args.away,
                             odds=tuple(args.odds) if args.odds else None)
    if args.json:
        print(json.dumps(pred.as_dict(), indent=2))
    else:
        print(pred.summary())
    if args.log:
        from football_stats import prediction_log as plog
        rec = plog.record(pred, fixture_date=args.date or "", dataset=args.dataset,
                          odds=tuple(args.odds) if args.odds else None)
        if not args.quiet:
            print(f"  logged as {rec.id} (pending result)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
