"""
Match models for football: Poisson regression, Elo ratings and Monte-Carlo simulation.

The workhorse is :class:`PoissonModel`. It estimates one attack and one defence rating
per team plus a home-advantage term, by maximum likelihood, using an iterative
proportional-fitting scheme (the same idea behind Dixon-Coles style models).

    lambda_home = exp(mu + home_advantage + attack[home] - defence[away])
    lambda_away = exp(mu                    + attack[away] - defence[home])

An optional Dixon-Coles ``rho`` corrects the four lowest-scoring draws/defeats, which
the plain Poisson model systematically mis-prices.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from . import data as d
from . import stats as st


# ---------------------------------------------------------------------------
# Poisson match model
# ---------------------------------------------------------------------------


@dataclass
class PoissonModel:
    """Attack/defence ratings fitted to a set of matches."""

    teams: list[str]
    attack: dict[str, float]
    defence: dict[str, float]
    mu: float
    home_advantage: float
    rho: float = 0.0
    n_matches: int = 0
    unseen_rating: float = 0.0

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        """Expected goals (xG) for a fixture.

        A team the model has never seen (e.g. a newly promoted side) is treated as a
        league-average team via ``unseen_rating`` (0.0 on the log scale).
        """
        ah = self.attack.get(home, self.unseen_rating)
        aa = self.attack.get(away, self.unseen_rating)
        dh = self.defence.get(home, self.unseen_rating)
        da = self.defence.get(away, self.unseen_rating)
        lh = math.exp(self.mu + self.home_advantage + ah - da)
        la = math.exp(self.mu + aa - dh)
        return lh, la

    def score_probabilities(self, home: str, away: str, max_goals: int = 10) -> list[list[float]]:
        """Joint probability matrix P(home goals = i, away goals = j)."""
        lh, la = self.lambdas(home, away)
        probs = [[st.poisson_pmf(i, lh) * st.poisson_pmf(j, la)
                  for j in range(max_goals + 1)] for i in range(max_goals + 1)]
        if self.rho:
            probs = _apply_dc(probs, lh, la, self.rho)
        return probs

    def match_probabilities(self, home: str, away: str, max_goals: int = 10) -> dict:
        """1X2 probabilities, over/under, BTTS and the most likely scoreline."""
        m = self.score_probabilities(home, away, max_goals)
        ph = sum(m[i][j] for i in range(len(m)) for j in range(len(m)) if i > j)
        pd = sum(m[i][j] for i in range(len(m)) for j in range(len(m)) if i == j)
        pa = sum(m[i][j] for i in range(len(m)) for j in range(len(m)) if i < j)
        over25 = sum(m[i][j] for i in range(len(m)) for j in range(len(m)) if i + j > 2.5)
        btts = sum(m[i][j] for i in range(len(m)) for j in range(len(m)) if i > 0 and j > 0)
        best = max(((i, j, m[i][j]) for i in range(len(m)) for j in range(len(m))),
                   key=lambda t: t[2])
        lh, la = self.lambdas(home, away)
        return {
            "home_win": ph, "draw": pd, "away_win": pa,
            "over_2_5": over25, "under_2_5": 1 - over25, "btts": btts,
            "most_likely_score": f"{best[0]}-{best[1]}",
            "most_likely_prob": best[2],
            "expected_home_goals": lh, "expected_away_goals": la,
        }

    def predict(self, home: str, away: str) -> dict:
        """Alias used by the evaluation examples."""
        return self.match_probabilities(home, away)

    def log_likelihood(self, matches: Sequence[d.Match]) -> float:
        """Log-likelihood of the observed scores under the model."""
        total = 0.0
        for m in matches:
            lh, la = self.lambdas(m.home, m.away)
            p = st.poisson_pmf(m.home_goals, lh) * st.poisson_pmf(m.away_goals, la)
            if self.rho:
                p *= _dc_tau(m.home_goals, m.away_goals, lh, la, self.rho)
            total += math.log(max(p, 1e-300))
        return total

    def ratings_table(self) -> list[dict]:
        """Attack/defence ratings sorted by attack."""
        rows = [{"team": t, "attack": self.attack[t], "defence": self.defence[t],
                 "goal_rate": math.exp(self.mu + self.attack[t]),
                 "concede_rate": math.exp(self.mu - self.defence[t])} for t in self.teams]
        return sorted(rows, key=lambda r: -r["attack"])

    def best_defence(self) -> str:
        """Team with the lowest expected goals conceded per match."""
        return max(self.teams, key=lambda t: self.defence[t])

    def worst_defence(self) -> str:
        return min(self.teams, key=lambda t: self.defence[t])


def _dc_tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor."""
    if x == 0 and y == 0:
        return 1.0 - lh * la * rho
    if x == 0 and y == 1:
        return 1.0 + lh * rho
    if x == 1 and y == 0:
        return 1.0 + la * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _apply_dc(probs: list[list[float]], lh: float, la: float, rho: float) -> list[list[float]]:
    out = [row[:] for row in probs]
    for x in range(2):
        for y in range(2):
            out[x][y] *= _dc_tau(x, y, lh, la, rho)
    return out


def fit_poisson(matches: Sequence[d.Match], iterations: int = 60,
                fit_rho: bool = True) -> PoissonModel:
    """Fit attack/defence ratings by maximum likelihood (Newton-Raphson / IRLS).

    The model is a Poisson GLM, so Newton's method uses the exact Hessian
    H = X' W X with W = diag(lambda_home, lambda_away). A tiny ridge term keeps the
    system non-singular along the (attack, defence) shift direction, which is then
    removed by centring the ratings after each step.
    """
    matches = list(matches)
    if not matches:
        raise ValueError("no matches to fit")
    teams = d.team_names(matches)
    t = len(teams)
    idx = {name: i for i, name in enumerate(teams)}
    p = 2 + 2 * t

    mu = math.log(sum(m.home_goals + m.away_goals for m in matches) / (2 * len(matches)))
    theta = [0.0] * p
    theta[0] = mu

    def unpack(th):
        return th[0], th[1], th[2:2 + t], th[2 + t:2 + 2 * t]

    def loglik_grad_hess(th):
        mu_, ha_, att, dfn = unpack(th)
        ll = 0.0
        grad = [0.0] * p
        H = [[0.0] * p for _ in range(p)]
        for m in matches:
            ih, ia = idx[m.home], idx[m.away]
            lh = math.exp(mu_ + ha_ + att[ih] - dfn[ia])
            la = math.exp(mu_ + att[ia] - dfn[ih])
            ll += m.home_goals * math.log(lh) - lh + m.away_goals * math.log(la) - la
            # design rows: [mu, ha, attack vector, defence vector]
            rh = m.home_goals - lh
            ra = m.away_goals - la
            grad[0] += rh + ra
            grad[1] += rh
            grad[2 + ih] += rh
            grad[2 + t + ia] -= rh
            grad[2 + ia] += ra
            grad[2 + t + ih] -= ra
            # Hessian: sum over the two responses of lambda * outer(x, x)
            # home response
            x = [0.0] * p
            x[0] = 1.0
            x[1] = 1.0
            x[2 + ih] = 1.0
            x[2 + t + ia] = -1.0
            for a in range(p):
                if x[a] == 0.0:
                    continue
                for b in range(a, p):
                    H[a][b] += lh * x[a] * x[b]
            # away response
            y = [0.0] * p
            y[0] = 1.0
            y[2 + ia] = 1.0
            y[2 + t + ih] = -1.0
            for a in range(p):
                if y[a] == 0.0:
                    continue
                for b in range(a, p):
                    H[a][b] += la * y[a] * y[b]
        for a in range(p):
            for b in range(a):
                H[a][b] = H[b][a]
        return ll, grad, H

    ll_prev = -math.inf
    for _ in range(iterations):
        ll, grad, H = loglik_grad_hess(theta)
        for a in range(p):
            H[a][a] += 1e-6
        step = st._solve(H, grad)
        # backtracking line search keeps the step stable
        scale = 1.0
        for _ in range(40):
            trial = [theta[i] + scale * step[i] for i in range(p)]
            ll_trial, _, _ = loglik_grad_hess(trial)
            if ll_trial >= ll:
                break
            scale *= 0.5
        theta = trial
        if abs(ll_trial - ll_prev) < 1e-9:
            break
        ll_prev = ll_trial

    mu_, ha_, att, dfn = unpack(theta)
    # identifiability: centre attack and defence, absorb the shift into mu
    ca = sum(att) / t
    cd = sum(dfn) / t
    att = [a - ca for a in att]
    dfn = [a - cd for a in dfn]
    mu_ = mu_ + ca - cd
    attack = {teams[i]: att[i] for i in range(t)}
    defence = {teams[i]: dfn[i] for i in range(t)}
    model = PoissonModel(teams, attack, defence, mu_, ha_, rho=0.0, n_matches=len(matches))

    if fit_rho:
        # Grid-search the Dixon-Coles rho by maximising log-likelihood.
        best_rho, best_ll = 0.0, model.log_likelihood(matches)
        rho = -0.20
        while rho <= 0.2001:
            model.rho = rho
            ll = model.log_likelihood(matches)
            if ll > best_ll:
                best_ll, best_rho = ll, rho
            rho += 0.005
        model.rho = best_rho
    return model


# ---------------------------------------------------------------------------
# Baselines (essential for honest model evaluation)
# ---------------------------------------------------------------------------


@dataclass
class BaselineModel:
    """Naive benchmark: every team is average. Predicts from league-wide goal rates."""

    home_lambda: float
    away_lambda: float
    name: str = "baseline"

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        return self.home_lambda, self.away_lambda

    def match_probabilities(self, home: str, away: str, max_goals: int = 10) -> dict:
        lh, la = self.lambdas(home, away)
        ph = pd = pa = 0.0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = st.poisson_pmf(i, lh) * st.poisson_pmf(j, la)
                if i > j:
                    ph += p
                elif i == j:
                    pd += p
                else:
                    pa += p
        return {"home_win": ph, "draw": pd, "away_win": pa,
                "over_2_5": 1 - st.poisson_cdf(2, lh + la), "btts": None,
                "expected_home_goals": lh, "expected_away_goals": la}

    def predict(self, home: str, away: str) -> dict:
        return self.match_probabilities(home, away)

    def log_likelihood(self, matches: Sequence[d.Match]) -> float:
        total = 0.0
        for m in matches:
            lh, la = self.lambdas(m.home, m.away)
            total += (m.home_goals * math.log(lh) - lh
                      + m.away_goals * math.log(la) - la)
        return total


def fit_baseline(matches: Sequence[d.Match]) -> BaselineModel:
    """League-average home and away goals per match."""
    hg = [m.home_goals for m in matches]
    ag = [m.away_goals for m in matches]
    return BaselineModel(st.mean(hg), st.mean(ag))


# ---------------------------------------------------------------------------
# Elo ratings
# ---------------------------------------------------------------------------


@dataclass
class Elo:
    """Elo ratings with home advantage and a goal-difference multiplier.

    E = 1 / (1 + 10 ** ((rating_opponent - rating_self) / 400))
    """

    k: float = 20.0
    home_advantage: float = 100.0
    initial: float = 1500.0
    ratings: dict[str, float] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def rating(self, team: str) -> float:
        return self.ratings.setdefault(team, self.initial)

    def expected(self, home: str, away: str) -> float:
        """Expected score (0..1) for the home team."""
        diff = (self.rating(home) + self.home_advantage) - self.rating(away)
        return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

    def update(self, match: d.Match) -> dict:
        """Update ratings after one match. Returns the details of the update."""
        rh, ra = self.rating(match.home), self.rating(match.away)
        exp_home = self.expected(match.home, match.away)
        actual = 1.0 if match.result == "H" else (0.5 if match.result == "D" else 0.0)
        diff = abs(match.home_goals - match.away_goals)
        multiplier = 1.0 if diff <= 1 else (1.5 if diff == 2 else (11.0 + diff) / 8.0)
        delta = self.k * multiplier * (actual - exp_home)
        self.ratings[match.home] = rh + delta
        self.ratings[match.away] = ra - delta
        record = {"date": match.date, "home": match.home, "away": match.away,
                  "score": f"{match.home_goals}-{match.away_goals}",
                  "expected_home": exp_home, "delta": delta,
                  "home_rating": self.ratings[match.home],
                  "away_rating": self.ratings[match.away]}
        self.history.append(record)
        return record

    def fit(self, matches: Sequence[d.Match]) -> "Elo":
        for m in sorted(matches, key=lambda m: (m.date, m.home)):
            self.update(m)
        return self

    def table(self) -> list[dict]:
        return sorted(({"team": t, "rating": r} for t, r in self.ratings.items()),
                      key=lambda r: -r["rating"])


# ---------------------------------------------------------------------------
# Monte-Carlo simulation
# ---------------------------------------------------------------------------


def simulate_matches(model: PoissonModel, fixtures: Sequence[tuple[str, str]],
                     seed: int | None = None) -> list[d.Match]:
    """Simulate fixtures by sampling goals from the model's Poisson distributions."""
    rng = random.Random(seed)
    out = []
    for home, away in fixtures:
        lh, la = model.lambdas(home, away)
        out.append(d.Match(date="sim", home=home, away=away,
                           home_goals=_poisson_sample(rng, lh),
                           away_goals=_poisson_sample(rng, la)))
    return out


def _poisson_sample(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm for sampling from a Poisson distribution."""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def simulate_season(model: PoissonModel, teams: Sequence[str], n_sim: int = 1000,
                    seed: int | None = None) -> dict:
    """Simulate a full double round-robin season `n_sim` times.

    Returns title probabilities, average points, and average league position.
    """
    schedule = d.round_robin_schedule(teams)
    rng = random.Random(seed)
    points = {t: [] for t in teams}
    positions = {t: [] for t in teams}
    titles = {t: 0 for t in teams}
    for _ in range(n_sim):
        sim_matches = simulate_matches(model, schedule, seed=rng.randrange(1 << 30))
        table = d.league_table(sim_matches)
        for i, row in enumerate(table):
            points[row["team"]].append(row["pts"])
            positions[row["team"]].append(i + 1)
            if i == 0:
                titles[row["team"]] += 1
    return {
        "title_prob": {t: titles[t] / n_sim for t in teams},
        "avg_points": {t: st.mean(points[t]) for t in teams},
        "avg_position": {t: st.mean(positions[t]) for t in teams},
        "n_sim": n_sim,
    }
