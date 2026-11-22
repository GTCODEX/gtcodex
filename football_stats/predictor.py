"""
The outcome predictor: turn statistical data into match-outcome probabilities.

This is the module that answers "what will happen in this match?". It combines three
independent signals and blends them:

1. **Poisson model**  — attack/defence ratings fitted to past results (optionally with
   time decay and shrinkage). Supplies 1X2, over/under, BTTS, expected goals, scorelines.
2. **Elo ratings**     — a rating system that reacts to every result; converted to 1X2
   with a logistic map fitted on the training data.
3. **Market odds**     — the bookmaker's implied probabilities (the single strongest
   public signal), when odds are supplied.

Blend weights are tuned on held-out data, and the final probabilities are calibrated so
that "60%" really means 60%. Nothing here is a crystal ball — :func:`backtest` measures
how accurate the predictions actually are.

Typical use
-----------
>>> from football_stats import data as d, predictor as p
>>> train = d.load_dataset("epl_2018_19")
>>> pred = p.fit_predictor(train)
>>> pred.predict("Arsenal", "Chelsea")
Prediction(home='Arsenal', away='Chelsea', home_win=0.4513, draw=0.2691, ...)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from . import data as d
from . import models as m
from . import stats as st

OUTCOMES = ("H", "D", "A")


# ---------------------------------------------------------------------------
# The prediction record
# ---------------------------------------------------------------------------


@dataclass
class Prediction:
    """A forecast for one match."""

    home: str
    away: str
    home_win: float
    draw: float
    away_win: float
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
    advice: str = ""

    @property
    def most_likely_outcome(self) -> str:
        return max(OUTCOMES, key=lambda o: getattr(self, {"H": "home_win",
                                                          "D": "draw",
                                                          "A": "away_win"}[o]))

    def probs(self) -> dict[str, float]:
        return {"H": self.home_win, "D": self.draw, "A": self.away_win}

    def as_dict(self) -> dict:
        return {
            "home": self.home, "away": self.away,
            "home_win": round(self.home_win, 4), "draw": round(self.draw, 4),
            "away_win": round(self.away_win, 4),
            "over_2_5": round(self.over_2_5, 4), "under_2_5": round(self.under_2_5, 4),
            "btts": round(self.btts, 4),
            "expected_home_goals": round(self.expected_home_goals, 3),
            "expected_away_goals": round(self.expected_away_goals, 3),
            "most_likely_score": self.most_likely_score,
            "most_likely_prob": round(self.most_likely_prob, 4),
            "most_likely_outcome": self.most_likely_outcome,
            "confidence": round(self.confidence, 4),
            "model_agreement": round(self.model_agreement, 4),
            "source": self.source, "advice": self.advice,
        }

    def summary(self) -> str:
        return (
            f"{self.home} vs {self.away}\n"
            f"  1X2            : {self.home_win:.1%} / {self.draw:.1%} / {self.away_win:.1%}"
            f"   (most likely: {self.most_likely_outcome}, {self.confidence:.1%} confident)\n"
            f"  expected goals : {self.expected_home_goals:.2f} - {self.expected_away_goals:.2f}"
            f"   (most likely score {self.most_likely_score}, {self.most_likely_prob:.1%})\n"
            f"  over/under 2.5 : {self.over_2_5:.1%} / {self.under_2_5:.1%}"
            f"   BTTS {self.btts:.1%}\n"
            f"  signals        : {self.source}   model agreement {self.model_agreement:.2f}"
            + (f"\n  note           : {self.advice}" if self.advice else "")
        )


# ---------------------------------------------------------------------------
# Signal 1: the Poisson model
# ---------------------------------------------------------------------------


def _poisson_signal(poisson_model: m.PoissonModel, home: str, away: str) -> dict:
    """Poisson signal, keyed by H / D / A like every other signal."""
    p = poisson_model.match_probabilities(home, away)
    return {
        "H": p["home_win"], "D": p["draw"], "A": p["away_win"],
        "over_2_5": p["over_2_5"], "under_2_5": p["under_2_5"], "btts": p["btts"],
        "expected_home_goals": p["expected_home_goals"],
        "expected_away_goals": p["expected_away_goals"],
        "most_likely_score": p["most_likely_score"],
        "most_likely_prob": p["most_likely_prob"],
    }


# ---------------------------------------------------------------------------
# Signal 2: Elo ratings, mapped to 1X2 with a logistic fitted on training data
# ---------------------------------------------------------------------------


@dataclass
class EloSignal:
    """Elo ratings plus the fitted mapping from rating difference to 1X2."""

    elo: m.Elo
    logistic_weights: list[float]
    draw_share: float
    source: str = "elo"

    def probs(self, home: str, away: str) -> dict[str, float]:
        diff = (self.elo.rating(home) + self.elo.home_advantage) - self.elo.rating(away)
        # the mapping was fitted on diff / 400 (see fit_elo_signal)
        z = self.logistic_weights[0] + self.logistic_weights[1] * (diff / 400.0)
        p_home = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        rest = 1.0 - p_home
        return {"H": p_home, "D": rest * self.draw_share,
                "A": rest * (1.0 - self.draw_share)}


def fit_elo_signal(matches: Sequence[d.Match], k: float = 20.0,
                   home_advantage: float = 100.0) -> EloSignal:
    """Fit Elo on the matches, then fit the rating-difference -> home-win map."""
    matches = sorted(matches, key=lambda x: (x.date, x.home))
    elo = m.Elo(k=k, home_advantage=home_advantage)
    diffs, outcomes = [], []
    for match in matches:
        diff = (elo.rating(match.home) + elo.home_advantage) - elo.rating(match.away)
        diffs.append([diff / 400.0])  # scale for numerical stability
        outcomes.append(1 if match.result == "H" else 0)
        elo.update(match)
    weights = st.logistic_regression(diffs, outcomes, lr=0.05, iters=4000)["weights"]
    draws = sum(1 for x in matches if x.result == "D")
    losses = sum(1 for x in matches if x.result == "A")
    draw_share = draws / (draws + losses) if (draws + losses) else 0.25
    return EloSignal(elo=elo, logistic_weights=weights, draw_share=draw_share)


# ---------------------------------------------------------------------------
# Signal 3: the betting market
# ---------------------------------------------------------------------------


def odds_to_probs(odds_home: float, odds_draw: float,
                  odds_away: float) -> dict[str, float]:
    """Decimal 1X2 odds -> probabilities, with the bookmaker's overround removed."""
    raw = [1.0 / odds_home, 1.0 / odds_draw, 1.0 / odds_away]
    overround = sum(raw)
    return {"H": raw[0] / overround, "D": raw[1] / overround,
            "A": raw[2] / overround}


def over_under_probs(over_odds: float, under_odds: float) -> dict[str, float]:
    """Decimal over/under odds -> probabilities, overround removed."""
    total = 1.0 / over_odds + 1.0 / under_odds
    return {"over_2_5": (1.0 / over_odds) / total,
            "under_2_5": (1.0 / under_odds) / total}


# ---------------------------------------------------------------------------
# The predictor
# ---------------------------------------------------------------------------


@dataclass
class PredictorConfig:
    """How the predictor is built."""

    decay: float = 0.99          # recency weighting for the Poisson fit
    ridge: float = 0.001         # shrinkage of ratings toward the league average
    fit_rho: bool = True         # Dixon-Coles low-score adjustment
    poisson_weight: float = 0.55
    elo_weight: float = 0.20
    odds_weight: float = 0.25    # only used when odds are supplied
    calibrate: bool = True       # temperature calibration on a holdout
    k: float = 20.0              # Elo K-factor
    home_advantage: float = 100.0
    holdout_frac: float = 0.25   # used to tune blend weights / calibration
    grid_step: float = 0.1       # blend-weight search resolution
    temp_step: float = 0.05      # calibration temperature search resolution


@dataclass
class Predictor:
    """A fitted, ready-to-use match predictor."""

    poisson: m.PoissonModel
    elo: EloSignal
    config: PredictorConfig
    temperature: float = 1.0
    source: str = "poisson+elo"
    n_train: int = 0
    diagnostics: dict = field(default_factory=dict)

    # -- prediction ---------------------------------------------------------

    def signals(self, home: str, away: str, odds: dict | None = None) -> dict[str, dict]:
        """The raw signal dictionaries from each model."""
        out = {"poisson": _poisson_signal(self.poisson, home, away),
               "elo": self.elo.probs(home, away)}
        if odds:
            out["odds"] = odds
        return out

    def predict(self, home: str, away: str,
                odds: tuple[float, float, float] | None = None,
                over_under_odds: tuple[float, float] | None = None) -> Prediction:
        """Forecast the outcome of one fixture.

        ``odds`` is a ``(home, draw, away)`` decimal-odds triple; when given, the
        market signal is blended in.
        """
        cfg = self.config
        sigs = {"poisson": _poisson_signal(self.poisson, home, away),
                "elo": self.elo.probs(home, away)}
        weights = {"poisson": cfg.poisson_weight, "elo": cfg.elo_weight, "odds": 0.0}
        sources = ["poisson", "elo"]
        if odds:
            market = odds_to_probs(*odds)
            if over_under_odds:
                market.update(over_under_probs(*over_under_odds))
            sigs["odds"] = market
            weights["odds"] = cfg.odds_weight
            sources.append("odds")

        # normalise the weights so they sum to 1
        total_w = sum(weights.values())
        weights = {k: v / total_w for k, v in weights.items()}

        probs = {o: sum(weights[k] * sigs[k][o] for k in sources) for o in OUTCOMES}
        # temperature calibration on the 1X2 logits
        if self.temperature != 1.0:
            logs = [math.log(max(probs[o], 1e-12)) / self.temperature for o in OUTCOMES]
            mx = max(logs)
            exps = [math.exp(z - mx) for z in logs]
            s = sum(exps)
            probs = {o: e / s for o, e in zip(OUTCOMES, exps)}
        # renormalise for safety
        s = sum(probs.values())
        probs = {o: p / s for o, p in probs.items()}

        p = sigs["poisson"]
        over_25 = p["over_2_5"]
        if "odds" in sigs and "over_2_5" in sigs["odds"]:
            over_25 = weights["odds"] * sigs["odds"]["over_2_5"] + \
                (1 - weights["odds"]) * p["over_2_5"]
        btts = p["btts"]

        confidence = max(probs.values())
        # agreement = share of the component models backing the same outcome
        votes = [max(OUTCOMES, key=lambda o: sigs[k][o]) for k in sources]
        top_vote = max(set(votes), key=votes.count)
        agreement = votes.count(top_vote) / len(votes)

        advice = ""
        if odds:
            value = {o: probs[o] * odds[{"H": 0, "D": 1, "A": 2}[o]]
                     for o in OUTCOMES}
            best = max(value, key=value.get)
            if value[best] > 1.10:
                advice = (f"model sees value in '{best}' "
                          f"(model {probs[best]:.1%} vs market {sigs['odds'][best]:.1%})")

        return Prediction(
            home=home, away=away,
            home_win=probs["H"], draw=probs["D"], away_win=probs["A"],
            over_2_5=over_25, under_2_5=1 - over_25, btts=btts,
            expected_home_goals=p["expected_home_goals"],
            expected_away_goals=p["expected_away_goals"],
            most_likely_score=p["most_likely_score"],
            most_likely_prob=p["most_likely_prob"],
            confidence=confidence, model_agreement=agreement,
            source="+".join(sources), advice=advice,
        )

    def predict_many(self, matches: Sequence[d.Match]) -> list[Prediction]:
        """Predict a list of fixtures, using each match's odds when available."""
        out = []
        for m in matches:
            odds = None
            if m.stats.get("home_odds") and m.stats.get("draw_odds") and m.stats.get("away_odds"):
                odds = (m.stat("home_odds"), m.stat("draw_odds"), m.stat("away_odds"))
            out.append(self.predict(m.home, m.away, odds=odds))
        return out


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------


def fit_predictor(train: Sequence[d.Match], config: PredictorConfig | None = None,
                  verbose: bool = False) -> Predictor:
    """Fit a predictor: Poisson model + Elo, with blend weights and calibration tuned
    on an internal holdout (the most recent ``holdout_frac`` of matches)."""
    cfg = config or PredictorConfig()
    matches = sorted(train, key=lambda m: (m.date, m.home))
    if len(matches) < 60:
        raise ValueError("need at least 60 matches to fit a predictor")
    holdout_n = max(20, int(len(matches) * cfg.holdout_frac))
    fit_matches, holdout = matches[:-holdout_n], matches[-holdout_n:]

    poisson = m.fit_poisson(fit_matches, decay=cfg.decay, ridge=cfg.ridge,
                            fit_rho=cfg.fit_rho)
    elo = fit_elo_signal(fit_matches, k=cfg.k, home_advantage=cfg.home_advantage)

    # --- tune the blend weights on the holdout --------------------------------
    signals = _holdout_signals(holdout, poisson, elo)
    best_w, best_ll = None, math.inf
    n_steps = int(round(1.0 / cfg.grid_step))
    steps = [i * cfg.grid_step for i in range(n_steps + 1)]
    for wp in steps:
        for we in steps:
            if wp + we > 1.0 + 1e-9:
                continue
            wo = max(0.0, 1.0 - wp - we)
            ll = _signals_log_loss(signals, wp, we, wo)
            if ll < best_ll:
                best_ll, best_w = ll, (wp, we, wo)
    wp, we, wo = best_w
    cfg.poisson_weight, cfg.elo_weight, cfg.odds_weight = wp, we, wo

    # --- temperature calibration on the holdout ------------------------------
    temp = 1.0
    if cfg.calibrate:
        best_t, best_ll = 1.0, math.inf
        t = 0.5
        while t <= 2.5001:
            ll = _signals_log_loss(signals, wp, we, wo, temperature=t)
            if ll < best_ll:
                best_ll, best_t = ll, t
            t += cfg.temp_step
        temp = best_t

    pred = Predictor(poisson=poisson, elo=elo, config=cfg, temperature=temp,
                     source="poisson+elo", n_train=len(fit_matches),
                     diagnostics={"holdout_log_loss": best_ll, "blend_weights": best_w})
    if verbose:
        print(f"  fitted on {len(fit_matches)} matches "
              f"(holdout {len(holdout)})")
        print(f"  blend weights: poisson {wp:.2f}  elo {we:.2f}  odds {wo:.2f}")
        print(f"  temperature: {temp:.2f}   holdout log-loss: {best_ll:.4f}")
    return pred


def _blend_probs(poisson_probs: dict, elo_probs: dict, wp: float, we: float,
                 temperature: float = 1.0) -> dict[str, float]:
    """Blend the Poisson and Elo 1X2 signals (weights renormalised)."""
    total = wp + we
    wp, we = (wp / total, we / total) if total else (0.5, 0.5)
    probs = {o: wp * poisson_probs[o] + we * elo_probs[o] for o in OUTCOMES}
    s = sum(probs.values())
    probs = {o: p / s for o, p in probs.items()}
    if temperature != 1.0:
        logs = [math.log(max(probs[o], 1e-12)) / temperature for o in OUTCOMES]
        mx = max(logs)
        exps = [math.exp(z - mx) for z in logs]
        s = sum(exps)
        probs = {o: e / s for o, e in zip(OUTCOMES, exps)}
    return probs


def _holdout_signals(holdout: Sequence[d.Match], poisson: m.PoissonModel,
                     elo: EloSignal) -> list[tuple]:
    """Pre-compute each holdout match's signals so the weight search is cheap."""
    out = []
    for m in holdout:
        pp = _poisson_signal(poisson, m.home, m.away)
        ep = elo.probs(m.home, m.away)
        mp = None
        if (m.stats.get("home_odds") and m.stats.get("draw_odds")
                and m.stats.get("away_odds")):
            mp = odds_to_probs(m.stat("home_odds"), m.stat("draw_odds"),
                               m.stat("away_odds"))
        out.append((m.result, pp, ep, mp))
    return out


def _signals_log_loss(signals: Sequence[tuple], wp: float, we: float, wo: float,
                      temperature: float = 1.0) -> float:
    """Log-loss for a candidate blend over pre-computed signals."""
    losses = []
    for result, pp, ep, mp in signals:
        if mp is not None and wo > 0:
            total = wp + we + wo
            probs = {o: (wp * pp[o] + we * ep[o] + wo * mp[o]) / total
                     for o in OUTCOMES}
        else:
            probs = _blend_probs(pp, ep, wp, we)
        s = sum(probs.values())
        probs = {o: p / s for o, p in probs.items()}
        if temperature != 1.0:
            logs = [math.log(max(probs[o], 1e-12)) / temperature for o in OUTCOMES]
            mx = max(logs)
            exps = [math.exp(z - mx) for z in logs]
            s2 = sum(exps)
            probs = {o: e / s2 for o, e in zip(OUTCOMES, exps)}
        losses.append(-math.log(max(probs[result], 1e-15)))
    return st.mean(losses)


# ---------------------------------------------------------------------------
# Honest evaluation
# ---------------------------------------------------------------------------


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion — a proper confidence interval."""
    if n == 0:
        return 0.0, 0.0
    z = st.normal_quantile(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def accuracy_report(predictions: Sequence[Prediction],
                    matches: Sequence[d.Match]) -> dict:
    """How good were these predictions? Accuracy, log-loss, Brier, calibration."""
    if len(predictions) != len(matches):
        raise ValueError("predictions and matches must have the same length")
    n = len(matches)
    correct = 0
    losses = []
    briers = []
    cal = []  # (predicted home-win prob, observed home win)
    over_correct = 0
    over_n = 0
    for pred, m in zip(predictions, matches):
        probs = pred.probs()
        correct += pred.most_likely_outcome == m.result
        losses.append(-math.log(max(probs[m.result], 1e-15)))
        briers.append(sum((probs[o] - (1 if m.result == o else 0)) ** 2 for o in OUTCOMES))
        cal.append((probs["H"], 1 if m.result == "H" else 0))
        if pred.over_2_5 > 0:
            over_n += 1
            over_correct += (pred.over_2_5 > 0.5) == (m.total_goals > 2.5)
    lo, hi = wilson_ci(correct, n)
    return {
        "n": n,
        "accuracy": correct / n,
        "accuracy_ci": (lo, hi),
        "log_loss": st.mean(losses),
        "brier": st.mean(briers),
        "over_2_5_accuracy": (over_correct / over_n) if over_n else None,
        "roc_auc": st.roc_auc([p.home_win for p in predictions],
                              [1 if m.result == "H" else 0 for m in matches]),
        "calibration": st.calibration([c[0] for c in cal], [c[1] for c in cal], bins=5),
    }


def backtest(matches: Sequence[d.Match], min_train: int = 190, step: int = 10,
             config: PredictorConfig | None = None, use_odds: bool = True,
             verbose: bool = True) -> dict:
    """Walk-forward evaluation: fit on the past, predict the next block, repeat.

    This is the honest measure of predictive accuracy — no future data leaks into the
    fit, exactly as it would in real life.
    """
    cfg = config or PredictorConfig()
    matches = sorted(matches, key=lambda m: (m.date, m.home))
    predictions: list[Prediction] = []
    outcomes: list[d.Match] = []
    folds = 0
    for start in range(min_train, len(matches), step):
        train = matches[:start]
        block = matches[start:start + step]
        pred = fit_predictor(train, config=cfg)
        for m in block:
            odds = None
            if use_odds and m.stats.get("home_odds") and m.stats.get("draw_odds"):
                odds = (m.stat("home_odds"), m.stat("draw_odds"), m.stat("away_odds"))
            predictions.append(pred.predict(m.home, m.away, odds=odds))
            outcomes.append(m)
        folds += 1
    report = accuracy_report(predictions, outcomes)
    report["folds"] = folds
    report["train_matches_per_fold"] = min_train
    report["predictions"] = predictions
    report["matches"] = outcomes
    report["vs_market"] = compare_with_market(predictions, outcomes)
    if verbose:
        print(f"  walk-forward over {folds} folds, {report['n']} matches")
        print(f"  accuracy {report['accuracy']:.1%} "
              f"(95% CI {report['accuracy_ci'][0]:.1%}–{report['accuracy_ci'][1]:.1%})")
        print(f"  log-loss {report['log_loss']:.4f}   "
              f"Brier {report['brier']:.4f}   "
              f"ROC-AUC {report['roc_auc']:.3f}")
        if report["over_2_5_accuracy"] is not None:
            print(f"  over/under 2.5 accuracy {report['over_2_5_accuracy']:.1%}")
    return report


def compare_with_market(predictions: Sequence[Prediction],
                        matches: Sequence[d.Match]) -> dict:
    """Same predictions, but scored against the bookmaker's implied probabilities."""
    pred_loss, market_loss = [], []
    for pred, m in zip(predictions, matches):
        if not (m.stats.get("home_odds") and m.stats.get("draw_odds")
                and m.stats.get("away_odds")):
            continue
        market = odds_to_probs(m.stat("home_odds"), m.stat("draw_odds"),
                               m.stat("away_odds"))
        probs = pred.probs()
        pred_loss.append(-math.log(max(probs[m.result], 1e-15)))
        market_loss.append(-math.log(max(market[m.result], 1e-15)))
    if not pred_loss:
        return {"n": 0, "model_log_loss": None, "market_log_loss": None}
    return {"n": len(pred_loss),
            "model_log_loss": st.mean(pred_loss),
            "market_log_loss": st.mean(market_loss)}


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def predict_season(train: Sequence[d.Match], season: Sequence[d.Match],
                   config: PredictorConfig | None = None) -> list[Prediction]:
    """Fit on ``train`` and predict every match of ``season``."""
    predictor = fit_predictor(train, config=config)
    return predictor.predict_many(season)
