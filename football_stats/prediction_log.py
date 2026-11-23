"""
A running log of every forecast the predictor issues, and how it actually turned out.

A model's claimed accuracy means nothing unless you write the forecasts down
*before* the match and score them afterwards. This module is that bookkeeping:

* :func:`record` — append a forecast (call it from the CLI or the web API).
* :func:`settle_from_datasets` — fill in the results once the matches are played.
* :func:`score` / :func:`calibration` / :func:`summary` — the honest scorecard.

The log is a single JSON document at ``data/prediction_log.json`` (repo root)::

    python -m football_stats.prediction_log --settle   # record results
    python -m football_stats.prediction_log            # print the scorecard

Nothing here is retrospective: a record is created with ``status="pending"`` and
only becomes ``settled`` once a real result is attached to it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

if __package__ in (None, ""):  # allow `python football_stats/prediction_log.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from . import data as d
from . import predictor as p
from . import stats as st

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
DEFAULT_LOG_PATH = REPO_ROOT / "data" / "prediction_log.json"

SCHEMA = 1

# datasets scanned, in order, when settling pending records
SETTLE_DATASETS = ("epl_2026_27", "epl_2025_26", "epl_2019_20", "epl_2018_19")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LogRecord:
    """One forecast, and (once played) the result it was judged against."""

    id: str
    created_at: str
    home: str
    away: str
    home_win: float
    draw: float
    away_win: float
    fixture_date: str = ""
    dataset: str = ""
    odds: list = field(default_factory=list)
    over_2_5: float = 0.0
    under_2_5: float = 0.0
    btts: float = 0.0
    expected_home_goals: float = 0.0
    expected_away_goals: float = 0.0
    most_likely_score: str = ""
    most_likely_prob: float = 0.0
    confidence: float = 0.0
    model_agreement: float = 1.0
    source: str = ""
    status: str = "pending"          # pending | settled | void
    result: str = ""                 # H / D / A once settled
    home_goals: int | None = None
    away_goals: int | None = None
    settled_at: str = ""
    settled_from: str = ""
    note: str = ""

    @property
    def most_likely_outcome(self) -> str:
        return max(p.OUTCOMES, key=lambda o: self.probs()[o])

    @property
    def settled(self) -> bool:
        return self.status == "settled" and self.result in p.OUTCOMES

    def probs(self) -> dict[str, float]:
        return {"H": self.home_win, "D": self.draw, "A": self.away_win}

    @property
    def total_goals(self) -> int | None:
        if self.home_goals is None or self.away_goals is None:
            return None
        return self.home_goals + self.away_goals

    @property
    def btts_actual(self) -> bool | None:
        if self.home_goals is None or self.away_goals is None:
            return None
        return self.home_goals > 0 and self.away_goals > 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "LogRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in raw.items() if k in known})


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def load_log(path: str | Path | None = None) -> list[LogRecord]:
    """Load the log. A missing or corrupt file is an empty log, not an error."""
    path = Path(path) if path else DEFAULT_LOG_PATH
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    records = raw.get("records", []) if isinstance(raw, dict) else raw
    out = []
    for item in records:
        try:
            out.append(LogRecord.from_dict(item))
        except TypeError:
            continue
    return out


def save_log(records: Sequence[LogRecord], path: str | Path | None = None) -> Path:
    path = Path(path) if path else DEFAULT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": SCHEMA, "updated_at": _now(),
               "records": [r.to_dict() for r in records]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def record(prediction: p.Prediction, *, fixture_date: str = "",
           dataset: str = "", odds: Sequence[float] | None = None,
           note: str = "", path: str | Path | None = None,
           now: str | None = None) -> LogRecord:
    """Append a forecast to the log and return the stored record."""
    rec = LogRecord(
        id=uuid.uuid4().hex[:8],
        created_at=now or _now(),
        home=prediction.home, away=prediction.away,
        home_win=prediction.home_win, draw=prediction.draw,
        away_win=prediction.away_win,
        fixture_date=fixture_date, dataset=dataset,
        odds=[float(x) for x in odds] if odds else [],
        over_2_5=prediction.over_2_5, under_2_5=prediction.under_2_5,
        btts=prediction.btts,
        expected_home_goals=prediction.expected_home_goals,
        expected_away_goals=prediction.expected_away_goals,
        most_likely_score=prediction.most_likely_score,
        most_likely_prob=prediction.most_likely_prob,
        confidence=prediction.confidence,
        model_agreement=prediction.model_agreement,
        source=prediction.source,
        note=note,
    )
    records = load_log(path)
    records.append(rec)
    save_log(records, path)
    return rec


def _key(home: str, away: str) -> tuple[str, str]:
    return (d.canonical_team(home).strip().lower(),
            d.canonical_team(away).strip().lower())


def index_matches(matches: Iterable[d.Match]) -> dict[tuple[str, str], d.Match]:
    return {_key(m.home, m.away): m for m in matches}


def settle_from_matches(records: Sequence[LogRecord], matches: Iterable[d.Match],
                        *, path: str | Path | None = None,
                        dataset_name: str = "", now: str | None = None) -> int:
    """Attach results to pending records. Returns how many were newly settled.

    When ``path`` is given the file there is authoritative: it is reloaded, the
    matching records are settled and the whole log written back. Passing a subset
    of the log therefore cannot silently drop the other records.
    """
    index = index_matches(matches)
    stamp = now or _now()
    targets = load_log(path) if path else list(records)
    n = 0
    for rec in targets:
        if rec.settled:
            continue
        m = index.get(_key(rec.home, rec.away))
        if m is None:
            continue
        rec.status = "settled"
        rec.result = m.result
        rec.home_goals = m.home_goals
        rec.away_goals = m.away_goals
        rec.settled_at = stamp
        rec.settled_from = dataset_name
        n += 1
    if n and path:
        save_log(targets, path)
    return n


def settle_from_datasets(records: Sequence[LogRecord] | None = None,
                         *, dataset_ids: Sequence[str] | None = None,
                         path: str | Path | None = None,
                         verbose: bool = True) -> int:
    """Settle pending records using the bundled datasets (most recent first)."""
    if path is None and records is None:
        path = DEFAULT_LOG_PATH
    ids = list(dataset_ids or SETTLE_DATASETS)
    total = 0
    for name in ids:
        try:
            matches = d.load_dataset(name)
        except KeyError:
            continue
        n = settle_from_matches(records or [], matches, path=path,
                                dataset_name=name)
        if n and verbose:
            print(f"  settled {n} from {name}")
        total += n
    return total


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score(records: Sequence[LogRecord]) -> dict:
    """Accuracy, log-loss, Brier and calibration summary for settled records."""
    done = [r for r in records if r.settled]
    n = len(done)
    out = {"n": n, "pending": sum(1 for r in records if r.status == "pending"),
           "accuracy": None, "accuracy_ci": (None, None), "log_loss": None,
           "brier": None, "over_under_accuracy": None, "btts_accuracy": None,
           "mean_confidence": None, "mean_abs_error": None}
    if not n:
        return out

    correct = 0
    losses: list[float] = []
    briers: list[float] = []
    over_ok = over_n = btts_ok = btts_n = 0
    for r in done:
        probs = r.probs()
        correct += r.most_likely_outcome == r.result
        losses.append(-math.log(max(probs[r.result], 1e-15)))
        briers.append(sum((probs[o] - (1.0 if o == r.result else 0.0)) ** 2
                          for o in p.OUTCOMES))
        total = r.total_goals
        if total is not None:
            over_n += 1
            over_ok += (r.over_2_5 > 0.5) == (total > 2.5)
        if r.btts_actual is not None:
            btts_n += 1
            btts_ok += (r.btts > 0.5) == r.btts_actual

    lo, hi = p.wilson_ci(correct, n)
    out.update({
        "accuracy": correct / n,
        "accuracy_ci": (lo, hi),
        "log_loss": st.mean(losses),
        "brier": st.mean(briers),
        "over_under_accuracy": (over_ok / over_n) if over_n else None,
        "btts_accuracy": (btts_ok / btts_n) if btts_n else None,
        "mean_confidence": st.mean([r.confidence for r in done]),
        "mean_abs_error": st.mean([abs(r.confidence - (1.0 if r.most_likely_outcome == r.result else 0.0))
                                   for r in done]),
    })
    return out


def calibration(records: Sequence[LogRecord], bins: int = 5) -> list[dict]:
    """Reliability of the picked outcome: predicted probability vs observed rate."""
    edges = [i / bins for i in range(bins + 1)]
    rows = [{"bin": (edges[i], edges[i + 1]), "n": 0, "predicted": [], "observed": 0}
            for i in range(bins)]
    for r in records:
        if not r.settled:
            continue
        prob = max(r.probs().values())
        idx = min(int(prob * bins), bins - 1)
        rows[idx]["n"] += 1
        rows[idx]["predicted"].append(prob)
        rows[idx]["observed"] += r.most_likely_outcome == r.result
    out = []
    for row in rows:
        out.append({
            "bin": [round(row["bin"][0], 2), round(row["bin"][1], 2)],
            "n": row["n"],
            "mean_pred": st.mean(row["predicted"]) if row["predicted"] else None,
            "observed": (row["observed"] / row["n"]) if row["n"] else None,
        })
    return out


def expected_calibration_error(records: Sequence[LogRecord], bins: int = 5) -> float | None:
    rows = [r for r in calibration(records, bins) if r["n"]]
    if not rows:
        return None
    total = sum(r["n"] for r in rows)
    return sum(r["n"] / total * abs(r["mean_pred"] - r["observed"]) for r in rows)


def summary(records: Sequence[LogRecord]) -> str:
    s = score(records)
    lines = [
        f"Prediction log: {len(records)} records "
        f"({s['n']} settled, {s['pending']} awaiting a result)",
    ]
    if not s["n"]:
        lines.append("  nothing settled yet — run --settle once the matches are played")
        return "\n".join(lines)
    lo, hi = s["accuracy_ci"]
    lines += [
        f"  1X2 accuracy     {s['accuracy']:.1%}   (95% CI {lo:.1%}-{hi:.1%})",
        f"  log-loss         {s['log_loss']:.4f}   (lower is better; 1.0986 = coin flip)",
        f"  Brier            {s['brier']:.4f}",
        f"  over/under 2.5   {s['over_under_accuracy']:.1%}" if s["over_under_accuracy"] is not None else "  over/under 2.5   n/a",
        f"  BTTS             {s['btts_accuracy']:.1%}" if s["btts_accuracy"] is not None else "  BTTS             n/a",
        f"  mean confidence  {s['mean_confidence']:.1%}",
        f"  calibration ECE  {expected_calibration_error(records):.3f}",
    ]
    lines.append("")
    lines.append("  Predicted probability vs how often the pick actually won:")
    for row in calibration(records):
        if row["n"]:
            lines.append(f"    {row['bin'][0]:.1f}-{row['bin'][1]:.1f}  n={row['n']:<4}"
                         f" predicted {row['mean_pred']:.2f}  observed {row['observed']:.2f}")
    return "\n".join(lines)


def table(records: Sequence[LogRecord]) -> str:
    rows = ["date       fixture                         pick  conf   result  score  status"]
    for r in records:
        result = r.result or "-"
        sc = (f"{r.home_goals}-{r.away_goals}" if r.home_goals is not None else "-")
        rows.append(f"{r.fixture_date or r.created_at[:10]:<10}  "
                    f"{r.home + ' v ' + r.away:<30}  {r.most_likely_outcome:<4}  "
                    f"{r.confidence:.0%}   {result:<6}  {sc:<5}  {r.status}")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m football_stats.prediction_log",
        description="Keep score: record forecasts and measure how they really did.",
    )
    ap.add_argument("--settle", action="store_true",
                    help="fill in results for pending records from the bundled datasets")
    ap.add_argument("--list", action="store_true", help="print every record")
    ap.add_argument("--path", help=f"log file (default: {DEFAULT_LOG_PATH})")
    args = ap.parse_args(argv)

    if args.settle:
        n = settle_from_datasets(path=args.path)
        print(f"settled {n} record(s)")
    records = load_log(args.path)
    if args.list:
        print(table(records))
        print()
    print(summary(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
