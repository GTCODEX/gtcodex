"""
Rebuild the bundled tidy datasets from their public sources.

The two historical seasons (2018/19, 2019/20) were normalised once and are
committed as-is. The two recent seasons change all the time, so they are rebuilt
by this module::

    python -m football_stats.prepare            # rebuild both recent seasons
    python -m football_stats.prepare --check    # report what would change

Sources
-------
* ``epl_2025_26`` — `AnishKhetani/premier-league-data` (a mirror of
  football-data.co.uk). Complete 380-match season with half-time scores.
* ``epl_2026_27`` — `oladeeayo/open-matchday`, refreshed daily. Results plus
  shots, shots on target, corners, fouls, cards and goal minutes.

Both are fetched with :mod:`football_stats.fetch` (standard library only, GitHub
contents API) and written to ``football_stats/datasets/``.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python football_stats/prepare.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from football_stats import data as d
from football_stats import fetch

DATASETS_DIR = d.DATASETS_DIR

CORE_COLUMNS = ("date", "round", "home", "away", "home_goals", "away_goals", "result")

# source name -> (output filename, season label)
BUILDS = {
    "premierleague_data_results": "epl_2025_26.csv",
    "openmatchday_epl_2026_27": "epl_2026_27.csv",
}

# Results the upstream source has not published yet. The builder merges these in
# and skips any fixture the source already has, so a rebuild never loses them.
SUPPLEMENTS = {
    "openmatchday_epl_2026_27": DATASETS_DIR / "supplement_2026_27.csv",
}


def _result(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"


def _round_labels(rows: list[dict]) -> None:
    """Label rows ``Matchday 1..N`` in blocks of 10 (a 20-team league round)."""
    for i, row in enumerate(rows):
        row["round"] = f"Matchday {i // 10 + 1}"


def _write(rows: list[dict], columns: list[str], path: Path) -> int:
    rows.sort(key=lambda r: (r["date"], r["home"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def build_epl_2025_26(raw: Path, out: Path | None = None) -> int:
    """2025/26 Premier League from the football-data.co.uk mirror (380 matches)."""
    out = out or DATASETS_DIR / "epl_2025_26.csv"
    rows: list[dict] = []
    with open(raw, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("season") != "2025-26":
                continue
            if not r.get("fthg") and not r.get("ftag"):
                continue
            rows.append({
                "date": r["date"],
                "round": "",
                "home": d.canonical_team(r["home_team"]),
                "away": d.canonical_team(r["away_team"]),
                "home_goals": int(r["fthg"]),
                "away_goals": int(r["ftag"]),
                "result": _result(int(r["fthg"]), int(r["ftag"])),
                "ht_home_goals": r.get("hthg", ""),
                "ht_away_goals": r.get("htag", ""),
                "ht_result": r.get("htr", ""),
            })
    _round_labels(rows)
    columns = ["date", "round", "home", "away", "home_goals", "away_goals", "result",
               "ht_home_goals", "ht_away_goals", "ht_result"]
    return _write(rows, columns, out)


def build_epl_2026_27(raw: Path, out: Path | None = None,
                      supplement: Path | None = None) -> int:
    """2026/27 Premier League from open-matchday (results + match statistics)."""
    out = out or DATASETS_DIR / "epl_2026_27.csv"
    if supplement is None:
        supplement = SUPPLEMENTS.get("openmatchday_epl_2026_27")
    stat_columns = (
        "ht_home_goals", "ht_away_goals", "ht_result",
        "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
        "home_fouls", "away_fouls", "home_corners", "away_corners",
        "home_yellow", "away_yellow", "home_red", "away_red", "goal_minutes",
    )
    source_columns = {
        "ht_home_goals": "ht_home", "ht_away_goals": "ht_away", "ht_result": "ht_result",
        "home_shots": "home_shots", "away_shots": "away_shots",
        "home_shots_on_target": "home_target", "away_shots_on_target": "away_target",
        "home_fouls": "home_fouls", "away_fouls": "away_fouls",
        "home_corners": "home_corners", "away_corners": "away_corners",
        "home_yellow": "home_yellow", "away_yellow": "away_yellow",
        "home_red": "home_red", "away_red": "away_red",
        "goal_minutes": "goal_minutes",
    }
    rows: list[dict] = []
    with open(raw, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("ft_result") not in ("H", "D", "A"):
                continue  # not yet played
            row = {
                "date": r["date"],
                "round": f"Matchday {r['gw']}",
                "home": d.canonical_team(r["home"]),
                "away": d.canonical_team(r["away"]),
                "home_goals": int(r["ft_home"]),
                "away_goals": int(r["ft_away"]),
                "result": r["ft_result"],
            }
            for dest, src in source_columns.items():
                row[dest] = r.get(src, "")
            rows.append(row)

    rows.extend(_read_supplement(supplement,
                                 {r["home"] + "|" + r["away"] for r in rows}))
    columns = ["date", "round", "home", "away", "home_goals", "away_goals", "result",
               *stat_columns]
    return _write(rows, columns, out)


def _read_supplement(path: Path | None, already_present: set[str]) -> list[dict]:
    """Rows from a hand-maintained supplement that the source does not have yet."""
    if not path or not path.exists():
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            home = d.canonical_team(r["home"])
            away = d.canonical_team(r["away"])
            if f"{home}|{away}" in already_present:
                continue
            hg, ag = int(r["home_goals"]), int(r["away_goals"])
            out.append({
                "date": r["date"], "round": "", "home": home, "away": away,
                "home_goals": hg, "away_goals": ag, "result": _result(hg, ag),
                **{col: "" for col in (
                    "ht_home_goals", "ht_away_goals", "ht_result",
                    "home_shots", "away_shots", "home_shots_on_target",
                    "away_shots_on_target", "home_fouls", "away_fouls",
                    "home_corners", "away_corners", "home_yellow", "away_yellow",
                    "home_red", "away_red", "goal_minutes")},
            })
    return out


def rebuild(which: str | None = None, force: bool = False,
            verbose: bool = True) -> dict[str, int]:
    """Fetch the sources and rebuild the datasets. Returns ``{name: n_matches}``."""
    results: dict[str, int] = {}
    for source, filename in BUILDS.items():
        if which and source != which:
            continue
        raw = fetch.fetch(source, force=force)
        if source == "premierleague_data_results":
            n = build_epl_2025_26(raw)
        else:
            n = build_epl_2026_27(raw)
        results[filename] = n
        if verbose:
            print(f"  {filename}: {n} matches")
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m football_stats.prepare",
        description="Rebuild the bundled recent-season datasets from their public sources.",
    )
    ap.add_argument("--source", choices=sorted(BUILDS), help="rebuild only this source")
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    results = rebuild(which=args.source, force=args.force, verbose=not args.quiet)
    if args.quiet:
        for name, n in results.items():
            print(f"{name}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
