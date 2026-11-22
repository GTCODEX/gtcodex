# Datasets

Two tidy CSV files, one row per match. Both are derived from public sources and are
bundled so the tutorials work offline.

## Files

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
[football-data.co.uk](https://www.football-data.co.uk/)).

| Column | Meaning |
|--------|---------|
| `date` | ISO date (`YYYY-MM-DD`) |
| `home`, `away` | canonical club names |
| `home_goals`, `away_goals` | full-time score |
| `result` | `H`, `D` or `A` |
| `ht_home_goals`, `ht_away_goals` | half-time score |
| `home_shots`, `away_shots` | total shots |
| `home_shots_on_target`, `away_shots_on_target` | shots on target |
| `home_corners`, `away_corners` | corners |
| `home_fouls`, `away_fouls` | fouls committed |
| `home_yellow`, `away_yellow`, `home_red`, `away_red` | cards |
| `home_odds`, `draw_odds`, `away_odds` | Bet365 decimal 1X2 odds |

## Verification

Both files were checked against the official records:

- **2018/19:** 1,072 goals (2.82 per game); Manchester City champions with 98 points,
  95 goals for and 23 against; Liverpool second with 97 points.
- **2019/20:** 1,034 goals; Liverpool champions with 99 points, 85 goals for and 33
  against.

## Club name normalisation

The two sources use different names for the same clubs (`Man City` vs
`Manchester City`, `Wolves` vs `Wolverhampton Wanderers`, ...). `data.py` maps them to
canonical names via `TEAM_ALIASES`, so the datasets can be joined across seasons.

## Re-downloading the originals

```bash
python -m football_stats.fetch
```

saves the source files to `datasets/original/` using only the Python standard library
(GitHub contents API). The bundled CSVs were produced by normalising dates, renaming
teams and selecting the columns above.

## Licences

- `jokecamp/FootballData` is published under the **MIT licence** (see its `LICENSE`).
- football-data.co.uk data is free for personal/educational use; check their site for
  terms if you redistribute.
- This package is for **educational** use.
