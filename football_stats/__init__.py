"""
football_stats — a zero-dependency learning package for statistics analysis of football data.

Submodules
----------
data    : load tidy match CSVs and compute league tables / splits
stats   : descriptive statistics, distributions, hypothesis tests, regression, evaluation
models  : Poisson match models, Elo ratings, Monte-Carlo simulation
fetch   : download the original public datasets from GitHub

Everything is pure Python 3.10+ standard library, in keeping with the rest of this repo.
"""

__version__ = "1.0.0"
__all__ = ["data", "stats", "models", "fetch"]
