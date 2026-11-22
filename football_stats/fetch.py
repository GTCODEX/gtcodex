"""
Download the original public datasets used by the tutorials.

The originals live in public GitHub repositories; this module fetches them with the
standard library only and stores them under ``football_stats/datasets/original/``.
The small, tidy CSVs shipped with the package were derived from these files.

Allowed hosts: api.github.com (the only route used here).
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ORIGINAL_DIR = PACKAGE_DIR / "datasets" / "original"

# name -> (repo, path inside repo, default branch)
SOURCES = {
    "footystats_epl_2018_19": (
        "jokecamp/FootballData",
        "FootyStats/england-premier-league-matches-2018-to-2019-stats.csv",
        "master",
    ),
    "football_data_epl_2019_20": (
        "jokecamp/FootballData",
        "football-data.co.uk/england/2019-2020/Premier.csv",
        "master",
    ),
}

UA = "football-stats-learning/1.0 (educational; stdlib urllib)"


def _api_url(repo: str, path: str, ref: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}"


def download(repo: str, path: str, dest: str | Path, ref: str = "master",
             force: bool = False) -> Path:
    """Download one file from a GitHub repo via the contents API (raw media type)."""
    dest = Path(dest)
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = _api_url(repo, path, ref)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/vnd.github.raw",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"failed to download {url}: HTTP {e.code}") from e
    dest.write_bytes(payload)
    return dest


def fetch(name: str, force: bool = False) -> Path:
    """Fetch one of the named source datasets."""
    if name not in SOURCES:
        raise KeyError(f"unknown source {name!r}; choose from {sorted(SOURCES)}")
    repo, path, ref = SOURCES[name]
    return download(repo, path, ORIGINAL_DIR / Path(path).name, ref=ref, force=force)


def fetch_all(force: bool = False) -> list[Path]:
    return [fetch(name, force=force) for name in SOURCES]


if __name__ == "__main__":
    for p in fetch_all():
        print(f"saved {p} ({p.stat().st_size:,} bytes)")
