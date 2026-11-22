"""
Data loading and wrangling for football statistics.

The datasets in ``football_stats/datasets/`` are tidy CSV files: one row per match,
one column per variable. This module turns them into a list of :class:`Match`
objects and provides the small set of helpers every analysis needs.

Source data
-----------
* ``epl_2018_19.csv`` — 380 Premier League matches, 2018/19, with xG, shots,
  possession, cards, corners and pre-match odds.
  Derived from https://github.com/jokecamp/FootballData (FootyStats scrape).
* ``epl_2019_20.csv`` — 380 Premier League matches, 2019/20, with shots, cards,
  corners, fouls and Bet365 odds. Derived from
  https://github.com/jokecamp/FootballData (football-data.co.uk mirror).

Both originals are re-downloaded by :mod:`football_stats.fetch`.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

PACKAGE_DIR = Path(__file__).resolve().parent
DATASETS_DIR = PACKAGE_DIR / "datasets"

DATASETS = {
    "epl_2018_19": DATASETS_DIR / "epl_2018_19.csv",
    "epl_2019_20": DATASETS_DIR / "epl_2019_20.csv",
    "epl_2025_26": DATASETS_DIR / "epl_2025_26.csv",
    "epl_2026_27": DATASETS_DIR / "epl_2026_27.csv",
}

# The two source datasets use different club names. Real-world data is full of
# these mismatches — normalising them is a core data-cleaning step.
TEAM_ALIASES = {
    "Bournemouth": "AFC Bournemouth",
    "Brighton": "Brighton & Hove Albion",
    "Leicester": "Leicester City",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Newcastle": "Newcastle United",
    "Norwich": "Norwich City",
    "Tottenham": "Tottenham Hotspur",
    "West Ham": "West Ham United",
    "Wolves": "Wolverhampton Wanderers",
    # short names used by the recent-season (openfootball) datasets
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
    "Coventry": "Coventry City",
}


def canonical_team(name: str) -> str:
    """Map a source-specific club name to the canonical name used everywhere."""
    name = name.strip()
    return TEAM_ALIASES.get(name, name)


@dataclass
class Match:
    """One football match. Only the score is guaranteed; everything else is optional."""

    date: str
    home: str
    away: str
    home_goals: int
    away_goals: int
    stats: dict = field(default_factory=dict)

    @property
    def result(self) -> str:
        """'H', 'D' or 'A' from the home team's perspective."""
        if self.home_goals > self.away_goals:
            return "H"
        if self.home_goals < self.away_goals:
            return "A"
        return "D"

    @property
    def total_goals(self) -> int:
        return self.home_goals + self.away_goals

    @property
    def btts(self) -> bool:
        """Both teams scored."""
        return self.home_goals > 0 and self.away_goals > 0

    def stat(self, name: str, default: float = 0.0) -> float:
        """Read an optional stat such as ``home_xg`` or ``home_shots``."""
        return float(self.stats.get(name, default))


def _to_int(v: str) -> int:
    return int(float(v)) if v not in ("", None) else 0


def _to_float(v: str) -> float:
    return float(v) if v not in ("", None) else 0.0


CORE_COLUMNS = ("date", "home", "away", "home_goals", "away_goals")


def load_csv(path: str | Path) -> list[Match]:
    """Load a tidy match CSV. Extra columns are kept in ``Match.stats``."""
    matches: list[Match] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats = {k: v for k, v in row.items() if k not in CORE_COLUMNS}
            matches.append(Match(
                date=row["date"].strip(),
                home=canonical_team(row["home"]),
                away=canonical_team(row["away"]),
                home_goals=_to_int(row["home_goals"]),
                away_goals=_to_int(row["away_goals"]),
                stats=stats,
            ))
    matches.sort(key=lambda m: (m.date, m.home))
    return matches


def load_dataset(name: str) -> list[Match]:
    """Load one of the bundled datasets by name (``epl_2018_19`` / ``epl_2019_20``)."""
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}; choose from {sorted(DATASETS)}")
    return load_csv(DATASETS[name])


def team_names(matches: Sequence[Match]) -> list[str]:
    """Sorted list of the teams present in a set of matches."""
    return sorted({m.home for m in matches} | {m.away for m in matches})


def split_by_date(matches: Sequence[Match], frac: float = 0.5) -> tuple[list[Match], list[Match]]:
    """Chronological split — the honest way to build train/test sets.

    The first ``frac`` of matches (by date) form the training set, the rest the test set.
    Never split randomly: later matches are what you actually want to predict.
    """
    ms = sorted(matches, key=lambda m: (m.date, m.home))
    cut = int(len(ms) * frac)
    return ms[:cut], ms[cut:]


def league_table(matches: Sequence[Match]) -> list[dict]:
    """Compute a league table (points, GD, goals for/against) from match results."""
    table: dict[str, dict] = {}

    def row(team: str) -> dict:
        return table.setdefault(team, {"team": team, "p": 0, "w": 0, "d": 0, "l": 0,
                                       "gf": 0, "ga": 0, "gd": 0, "pts": 0})

    for m in matches:
        h, a = row(m.home), row(m.away)
        h["p"] += 1
        a["p"] += 1
        h["gf"] += m.home_goals
        h["ga"] += m.away_goals
        a["gf"] += m.away_goals
        a["ga"] += m.home_goals
        if m.result == "H":
            h["w"] += 1
            a["l"] += 1
            h["pts"] += 3
        elif m.result == "A":
            a["w"] += 1
            h["l"] += 1
            a["pts"] += 3
        else:
            h["d"] += 1
            a["d"] += 1
            h["pts"] += 1
            a["pts"] += 1
    for r in table.values():
        r["gd"] = r["gf"] - r["ga"]
    return sorted(table.values(), key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))


def team_matches(matches: Sequence[Match], team: str) -> list[Match]:
    """All matches played by one team."""
    return [m for m in matches if m.home == team or m.away == team]


def goals_for(matches: Sequence[Match], team: str) -> list[int]:
    return [m.home_goals if m.home == team else m.away_goals for m in team_matches(matches, team)]


def goals_against(matches: Sequence[Match], team: str) -> list[int]:
    return [m.away_goals if m.home == team else m.home_goals for m in team_matches(matches, team)]


def home_advantage(matches: Sequence[Match]) -> dict:
    """Home vs away goals, wins and points — the classic first analysis."""
    hg = [m.home_goals for m in matches]
    ag = [m.away_goals for m in matches]
    hw = sum(1 for m in matches if m.result == "H")
    draws = sum(1 for m in matches if m.result == "D")
    aw = sum(1 for m in matches if m.result == "A")
    n = len(matches)
    return {
        "home_goals": sum(hg), "away_goals": sum(ag),
        "home_goals_per_game": sum(hg) / n, "away_goals_per_game": sum(ag) / n,
        "home_wins": hw, "draws": draws, "away_wins": aw,
        "home_win_pct": hw / n, "draw_pct": draws / n, "away_win_pct": aw / n,
    }


def round_robin_schedule(teams: Sequence[str]) -> list[tuple[str, str]]:
    """A double round-robin schedule (home and away) using the circle method."""
    teams = list(teams)
    if len(teams) % 2:
        teams.append(None)  # bye
    n = len(teams)
    half = n // 2
    schedule = []
    for r in range(n - 1):
        for i in range(half):
            a, b = teams[i], teams[n - 1 - i]
            if a and b:
                schedule.append((a, b) if r % 2 == 0 else (b, a))
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    second_leg = [(away, home) for home, away in schedule]
    return schedule + second_leg


def to_csv(matches: Sequence[Match], path: str | Path) -> None:
    """Write matches back to a tidy CSV (round-trip helper)."""
    if not matches:
        raise ValueError("no matches to write")
    cols = list(CORE_COLUMNS) + list(matches[0].stats)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for m in matches:
            w.writerow([m.date, m.home, m.away, m.home_goals, m.away_goals]
                       + [m.stats.get(c, "") for c in m.stats])


def parse_date(s: str) -> date:
    return date.fromisoformat(s)
