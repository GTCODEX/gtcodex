"""
Core statistics for football analysis — pure Python standard library.

Covers the four pillars used throughout the tutorials:

1. Descriptive statistics   : mean, median, spread, percentiles, histograms
2. Distributions             : normal, Student-t, chi-square, Poisson (+ incomplete beta/gamma)
3. Inference                 : confidence intervals, bootstrap, t-test, Mann-Whitney, chi-square GOF
4. Modelling & evaluation    : linear / logistic regression, correlation, Brier, log-loss, ROC-AUC

Every function is small enough to read in one sitting, so you can see exactly how the
maths is implemented. No numpy, no scipy, no pandas.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence

# ---------------------------------------------------------------------------
# 1. Descriptive statistics
# ---------------------------------------------------------------------------


def mean(xs: Sequence[float]) -> float:
    """Arithmetic mean."""
    xs = list(xs)
    if not xs:
        raise ValueError("mean of empty sequence")
    return sum(xs) / len(xs)


def median(xs: Sequence[float]) -> float:
    """Median (middle value; average of the two middle values for even n)."""
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        raise ValueError("median of empty sequence")
    mid = n // 2
    if n % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2


def mode(xs: Sequence[float]) -> float:
    """Most frequent value (first one encountered wins on ties)."""
    counts: dict[float, int] = {}
    for x in xs:
        counts[x] = counts.get(x, 0) + 1
    if not counts:
        raise ValueError("mode of empty sequence")
    best, best_n = None, -1
    for x in xs:  # preserve first-encountered order
        if counts[x] > best_n:
            best, best_n = x, counts[x]
    return best


def variance(xs: Sequence[float], ddof: int = 1) -> float:
    """Sample variance (ddof=1, the usual unbiased estimator)."""
    xs = list(xs)
    n = len(xs)
    if n - ddof <= 0:
        raise ValueError("not enough data for ddof")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def stdev(xs: Sequence[float], ddof: int = 1) -> float:
    """Sample standard deviation."""
    return math.sqrt(variance(xs, ddof))


def percentile(xs: Sequence[float], p: float) -> float:
    """Linear-interpolation percentile, p in [0, 100]."""
    if not 0 <= p <= 100:
        raise ValueError("p must be in [0, 100]")
    xs = sorted(xs)
    if not xs:
        raise ValueError("percentile of empty sequence")
    if len(xs) == 1:
        return xs[0]
    rank = (p / 100) * (len(xs) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return xs[lo]
    frac = rank - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def summary(xs: Sequence[float]) -> dict:
    """A one-call descriptive summary — the starting point of every analysis."""
    xs = list(xs)
    return {
        "n": len(xs),
        "mean": mean(xs),
        "median": median(xs),
        "stdev": stdev(xs),
        "min": min(xs),
        "max": max(xs),
        "p10": percentile(xs, 10),
        "p90": percentile(xs, 90),
    }


def histogram(xs: Sequence[float], bins: int = 10) -> list[tuple[float, float, int]]:
    """Bin data into `bins` equal-width buckets -> [(low, high, count), ...]."""
    xs = list(xs)
    if not xs:
        return []
    lo, hi = min(xs), max(xs)
    if lo == hi:
        return [(lo, hi, len(xs))]
    width = (hi - lo) / bins
    counts = [0] * bins
    for x in xs:
        idx = int((x - lo) / width)
        if idx == bins:  # x == hi
            idx -= 1
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, c) for i, c in enumerate(counts)]


def zscore(xs: Sequence[float]) -> list[float]:
    """Standardise to mean 0, sd 1."""
    m, s = mean(xs), stdev(xs)
    return [(x - m) / s for x in xs]


# ---------------------------------------------------------------------------
# 2. Probability distributions
# ---------------------------------------------------------------------------


def normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    """Student-t cumulative distribution function."""
    if df <= 0:
        raise ValueError("df must be positive")
    x = df / (df + t * t)
    p = 0.5 * _betai(df / 2.0, 0.5, x)
    return 1.0 - p if t >= 0 else p


def t_sf(t: float, df: float) -> float:
    """Survival function P(T > t) for Student-t."""
    return 1.0 - t_cdf(t, df)


def _gammaincc(a: float, x: float) -> float:
    """Regularised upper incomplete gamma function Q(a, x) (Numerical Recipes)."""
    if x < 0 or a <= 0:
        raise ValueError("invalid arguments")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        # series representation for P, then Q = 1 - P
        ap, total, delta = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 3e-12:
                break
        p = total * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return 1.0 - p
    # continued fraction for Q
    FPMIN = 1e-300
    b = x + 1.0 - a
    c = 1.0 / FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < FPMIN:
            d = FPMIN
        c = b + an / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x: float, df: float) -> float:
    """Chi-square survival function P(X > x) with df degrees of freedom."""
    if x < 0:
        return 1.0
    return _gammaincc(df / 2.0, x / 2.0)


def poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lambda)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1.0))


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lambda)."""
    return sum(poisson_pmf(i, lam) for i in range(0, k + 1))


def fit_poisson(xs: Sequence[float]) -> float:
    """Maximum-likelihood estimate of lambda: the sample mean."""
    return mean(xs)


def dpois_table(lam: float, kmax: int = 10) -> list[tuple[int, float]]:
    """Poisson probabilities for k = 0..kmax."""
    return [(k, poisson_pmf(k, lam)) for k in range(kmax + 1)]


# ---------------------------------------------------------------------------
# 3. Inference
# ---------------------------------------------------------------------------


def ci_normal_mean(xs: Sequence[float], confidence: float = 0.95) -> tuple[float, float]:
    """Confidence interval for a mean using the normal approximation (large n)."""
    z = normal_quantile(1 - (1 - confidence) / 2)
    m, s = mean(xs), stdev(xs)
    half = z * s / math.sqrt(len(xs))
    return m - half, m + half


def normal_quantile(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def bootstrap_ci(xs: Sequence[float], stat: Callable[[Sequence[float]], float] = mean,
                 n_boot: int = 2000, confidence: float = 0.95,
                 seed: int | None = None) -> tuple[float, float]:
    """Bootstrap percentile confidence interval — no distributional assumptions."""
    xs = list(xs)
    if not xs:
        raise ValueError("empty sequence")
    rng = random.Random(seed)
    stats = []
    for _ in range(n_boot):
        sample = [xs[rng.randrange(len(xs))] for _ in range(len(xs))]
        stats.append(stat(sample))
    stats.sort()
    lo = percentile(stats, 100 * (1 - confidence) / 2)
    hi = percentile(stats, 100 * (1 + confidence) / 2)
    return lo, hi


def welch_ttest(a: Sequence[float], b: Sequence[float]) -> dict:
    """Welch's two-sample t-test (unequal variances). Returns t, df and two-sided p."""
    a, b = list(a), list(b)
    ma, mb = mean(a), mean(b)
    va, vb = variance(a), variance(b)
    na, nb = len(a), len(b)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return {"t": 0.0, "df": na + nb - 2, "p": 1.0, "mean_a": ma, "mean_b": mb}
    t = (ma - mb) / se
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    p = 2 * t_sf(abs(t), df)
    return {"t": t, "df": df, "p": p, "mean_a": ma, "mean_b": mb}


def mannwhitneyu(a: Sequence[float], b: Sequence[float]) -> dict:
    """Mann-Whitney U test (rank-based, no normality assumption)."""
    a, b = list(a), list(b)
    combined = [(x, 0) for x in a] + [(x, 1) for x in b]
    combined.sort(key=lambda t: t[0])
    # average ranks for ties
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    r1 = sum(r for r, (_, g) in zip(ranks, combined) if g == 0)
    n1, n2 = len(a), len(b)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)
    mu = n1 * n2 / 2.0
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    z = (u - mu) / sigma if sigma else 0.0
    p = 2 * (1 - normal_cdf(abs(z)))
    return {"u": u, "z": z, "p": p, "u1": u1, "u2": u2}


def chi_square_gof(observed: Sequence[float], expected: Sequence[float]) -> dict:
    """Chi-square goodness-of-fit test: does `observed` follow `expected`?"""
    if len(observed) != len(expected):
        raise ValueError("observed and expected must have the same length")
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)
    dof = len([e for e in expected if e > 0]) - 1
    return {"chi2": chi2, "df": dof, "p": chi2_sf(chi2, dof) if dof > 0 else 1.0}


# ---------------------------------------------------------------------------
# 4. Correlation and regression
# ---------------------------------------------------------------------------


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """Pearson product-moment correlation coefficient r."""
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation (Pearson on ranks)."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + 1 + j + 1) / 2.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(ranks(list(x)), ranks(list(y)))


def linregress(x: Sequence[float], y: Sequence[float]) -> dict:
    """Ordinary least squares simple linear regression y = a + b*x."""
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("need at least two paired observations")
    mx, my = mean(x), mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    b = sxy / sxx if sxx else 0.0
    a = my - b * mx
    yhat = [a + b * v for v in x]
    ss_res = sum((v - h) ** 2 for v, h in zip(y, yhat))
    ss_tot = sum((v - my) ** 2 for v in y)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    n = len(x)
    se_b = math.sqrt(ss_res / (n - 2) / sxx) if sxx and n > 2 else 0.0
    t = b / se_b if se_b else 0.0
    return {"intercept": a, "slope": b, "r": math.copysign(math.sqrt(r2), b),
            "r2": r2, "n": n, "se_slope": se_b, "t_slope": t,
            "p_slope": 2 * t_sf(abs(t), n - 2) if n > 2 else 1.0}


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[pivot] = M[pivot], M[col]
        for r in range(col + 1, n):
            f = M[r][col] / M[col][col]
            for c in range(col, n + 1):
                M[r][c] -= f * M[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / M[r][r]
    return x


def linear_regression(X: Sequence[Sequence[float]], y: Sequence[float]) -> dict:
    """Multiple OLS regression y = b0 + b1*x1 + ... + bk*xk (normal equations)."""
    X, y = [list(r) for r in X], list(y)
    n, k = len(X), len(X[0])
    if n != len(y):
        raise ValueError("X and y must have the same number of rows")
    Xd = [[1.0] + row for row in X]
    p = k + 1
    A = [[sum(Xd[i][a] * Xd[i][b] for i in range(n)) for b in range(p)] for a in range(p)]
    rhs = [sum(Xd[i][a] * y[i] for i in range(n)) for a in range(p)]
    beta = _solve(A, rhs)
    yhat = [sum(beta[j] * Xd[i][j] for j in range(p)) for i in range(n)]
    my = mean(y)
    ss_res = sum((y[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((v - my) ** 2 for v in y)
    return {"coef": beta, "r2": 1 - ss_res / ss_tot if ss_tot else 0.0,
            "rmse": math.sqrt(ss_res / n), "n": n, "k": k}


def logistic_regression(X: Sequence[Sequence[float]], y: Sequence[int],
                        lr: float = 0.1, iters: int = 2000, l2: float = 1e-4) -> dict:
    """Binary logistic regression via gradient descent. y must be 0/1."""
    X, y = [list(r) for r in X], list(y)
    n, k = len(X), len(X[0])
    if n != len(y):
        raise ValueError("X and y must have the same number of rows")
    Xd = [[1.0] + row for row in X]
    p = k + 1
    w = [0.0] * p
    for _ in range(iters):
        grad = [0.0] * p
        for i in range(n):
            z = sum(w[j] * Xd[i][j] for j in range(p))
            pred = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            err = pred - y[i]
            for j in range(p):
                grad[j] += err * Xd[i][j]
        for j in range(p):
            w[j] -= lr * (grad[j] / n + l2 * w[j])
    return {"weights": w, "n": n, "k": k}


def predict_logistic(weights: Sequence[float], x: Sequence[float]) -> float:
    """Predicted probability from logistic weights."""
    z = weights[0] + sum(w * v for w, v in zip(weights[1:], x))
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


# ---------------------------------------------------------------------------
# 5. Model evaluation (probabilistic forecasts)
# ---------------------------------------------------------------------------


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error of a probability forecast (lower is better)."""
    if len(probabilities) != len(outcomes):
        raise ValueError("length mismatch")
    return mean([(p - o) ** 2 for p, o in zip(probabilities, outcomes)])


def log_loss(probabilities: Sequence[float], outcomes: Sequence[int], eps: float = 1e-15) -> float:
    """Negative log-likelihood of a probability forecast (lower is better)."""
    if len(probabilities) != len(outcomes):
        raise ValueError("length mismatch")
    total = 0.0
    for p, o in zip(probabilities, outcomes):
        p = min(max(p, eps), 1 - eps)
        total += math.log(p) if o == 1 else math.log(1 - p)
    return -total / len(outcomes)


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Area under the ROC curve via the Mann-Whitney U statistic."""
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        raise ValueError("need both positive and negative examples")
    return mannwhitneyu(pos, neg)["u1"] / (len(pos) * len(neg))


def calibration(probabilities: Sequence[float], outcomes: Sequence[int],
                bins: int = 10) -> list[dict]:
    """Compare mean predicted probability with observed frequency per bin."""
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(probabilities) if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if not idx:
            out.append({"bin": (lo, hi), "n": 0, "mean_pred": None, "observed": None})
            continue
        out.append({"bin": (lo, hi), "n": len(idx),
                    "mean_pred": mean([probabilities[i] for i in idx]),
                    "observed": mean([outcomes[i] for i in idx])})
    return out


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Root mean squared error."""
    return math.sqrt(mean([(a - p) ** 2 for a, p in zip(actual, predicted)]))


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean absolute error."""
    return mean([abs(a - p) for a, p in zip(actual, predicted)])
