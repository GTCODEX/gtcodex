# Datasets

Tidy CSV files, one row per match, derived from public sources and bundled so the
predictor works offline. Every club name is canonical (see `TEAM_ALIASES` in
`data.py`), so seasons can be joined.

## Files

### `epl_2026_27.csv` — 2026/27 Premier League (current season)

Rebuilt from [oladeeayo/open-matchday](https://github.com/oladeeayo/open-matchday),
which refreshes daily. Only played matches are included.

| Column | Meaning |
|--------|---------|
| `date`, `round`, `home`, `away` | fixture |
| `home_goals`, `away_goals`, `result` | full-time score (`H`/`D`/`A`) |
| `ht_home_goals`, `ht_away_goals`, `ht_result` | half-time score |
| `home_shots`, `away_shots` | total shots |
| `home_shots_on_target`, `away_shots_on_target` | shots on target |
| `home_corners`, `away_corners` | corners |
| `home_fouls`, `away_fouls` | fouls committed |
| `home_yellow`, `away_yellow`, `home_red`, `away_red` | cards |
| `goal_minutes` | comma-separated goal minutes (unattributed) |

**This file changes as the season progresses.** Rebuild it with
`python -m football_stats.prepare`.

### `supplement_2026_27.csv` — results the source has not published yet

The upstream feed sometimes lags a day. Any fixture that has been played but is
missing from the source can be added here; the builder merges it in and skips
fixtures the source already has, so a rebuild never loses it. Delete rows once the
source catches up.

### `epl_2025_26.csv` — 2025/26 Premier League (380 matches, complete)

Rebuilt from [AnishKhetani/premier-league-data](https://github.com/AnishKhetani/premier-league-data)
(a mirror of football-data.co.uk). Columns: `date`, `round`, `home`, `away`,
`home_goals`, `away_goals`, `result`, `ht_home_goals`, `ht_away_goals`, `ht_result`.

An earlier version of this file came from
[openfootball/football.json](https://github.com/openfootball/football.json), whose
2025/26 file is missing 27 matches; the two sources agree on every match they
share.

### `epl_2018_19.csv` — 2018/19 Premier League (380 matches)

Derived from `FootyStats/england-premier-league-matches-2018-to-2019-stats.csv` in
[jokecamp/FootballData](https://github.com/jokecamp/FootballData).

| Column | Meaning |
|--------|---------|
| `date` | ISO date (`YYYY-MM-DD`) |
| `home`, `away` | canonical club names |
| `home_goals`, `away_goals` | full-time score |
| `home_xg`, `away_xg` | expected goals |
| `home_shots`, `away_shots` | total shots |
| `home_shots_on_target`, `away_shots_on_target` | shots on target |
| `home_possession`, `away_possession` | possession % |
| `home_corners`, `away_corners` | corners |
| `home_yellow`, `away_yellow`, `home_red`, `away_red` | cards |
| `home_odds`, `draw_odds`, `away_odds` | decimal 1X2 odds |
| `stadium` | venue |

### `epl_2019_20.csv` — 2019/20 Premier League (380 matches)

Derived from `football-data.co.uk/england/2019-2020/Premier.csv` in
[jokecamp/FootballData](https://github.com/jokecamp/FootballData) (original source:
[football-data.co.uk](https://www.football-data.co.uk/)). Same columns as 2018/19
minus xG and possession.

## Composite datasets

`data.COMPOSITE_DATASETS` defines `epl_recent` = `epl_2025_26` + `epl_2026_27`
(488 matches). It contains 23 clubs — the three relegated after 2025/26
(Burnley, West Ham, Wolves) and the three promoted for 2026/27 (Coventry, Hull,
Ipswich) each have data for one season only. Use it for predicting the current
campaign: more history, and it actually includes this season's results.

```python
from football_stats import data as d
train = d.load_dataset("epl_recent")
```

## Verification

- **2018/19:** 1,072 goals (2.82 per game); Manchester City champions with 98 points.
- **2019/20:** 1,034 goals; Liverpool champions with 99 points.
- **2025/26:** 380 matches; Arsenal champions with 85 points. The 353 matches shared
  with the openfootball file agree exactly.
- **2026/27:** cross-checked against openfootball — all 41 fixtures present in both
  sources agree on the score.

## Rebuilding

```bash
python -m football_stats.prepare            # rebuild both recent seasons
python -m football_stats.prepare --force    # re-download the sources first
python -m football_stats.fetch              # only download the raw originals
```

## Licences

- `jokecamp/FootballData` is published under the **MIT licence** (see its `LICENSE`).
- football-data.co.uk data is free for personal/educational use; check their site for
  terms if you redistribute.
- `oladeeayo/open-matchday` is free for **non-commercial use with attribution**; see
  its `DISCLAIMER.md`. Please credit it if you publish anything built on this data.
- `AnishKhetani/premier-league-data` mirrors football-data.co.uk and carries its
  `DATA_LICENSE.md`.
- This package is for **educational** use.
