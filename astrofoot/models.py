"""Learning core: market control model (M0), offset softmax with L1/L2 (M1, M2), metrics.

Outcome classes are ordered from team1's point of view: 0 = team1 wins, 1 = draw, 2 = team2 wins.
Astrological features enter only as a *shift* on the market's log-probabilities:

    logits = log p_M0 + [ X w ,  X v ,  -X w ]

so `w` moves probability between team1 and team2 (what helps one side hurts the other) and
`v` moves probability into or out of the draw.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

EPS = 1e-12
SD_FLOOR = 0.05     # features live on [0,1] or [-1,1]; a tinier training sd means "barely seen"
Z_CLIP = 8.0        # slow-planet configurations can leave their training range in a test season
MIN_ACTIVE = 200    # a primitive must be clearly active in this many training matches to be used


# ---------------------------------------------------------------- metrics
def onehot(y: np.ndarray) -> np.ndarray:
    return np.eye(3)[y]


def rps(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    Y = onehot(y)
    c = np.cumsum(P, 1)[:, :2] - np.cumsum(Y, 1)[:, :2]
    return 0.5 * (c ** 2).sum(1)


def logloss(P, y):
    return -np.log(np.clip(P[np.arange(len(y)), y], EPS, 1))


def brier(P, y):
    return ((P - onehot(y)) ** 2).sum(1)


def scores(P, y) -> dict:
    return {"rps": float(rps(P, y).mean()), "logloss": float(logloss(P, y).mean()),
            "brier": float(brier(P, y).mean()), "accuracy": float((P.argmax(1) == y).mean()),
            "n": int(len(y))}


def block_bootstrap_delta(loss_a, loss_b, blocks, B=1000, seed=0) -> dict:
    """Mean(loss_a - loss_b) with a 95% CI, resampling whole blocks (match days)."""
    d = pd.Series(loss_a - loss_b).groupby(np.asarray(blocks))
    sums, counts = d.sum().to_numpy(), d.size().to_numpy()
    rng = np.random.default_rng(seed)
    k = len(sums)
    idx = rng.integers(0, k, (B, k))
    boots = sums[idx].sum(1) / counts[idx].sum(1)
    est = sums.sum() / counts.sum()
    return {"delta": float(est), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "p_model_better": float((boots < 0).mean())}


def ece(P, y, bins=10) -> float:
    conf = P.max(1)
    hit = (P.argmax(1) == y)
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for a, b in zip(edges[:-1], edges[1:]):
        m = (conf > a) & (conf <= b)
        if m.any():
            tot += m.mean() * abs(hit[m].mean() - conf[m].mean())
    return float(tot)


# ---------------------------------------------------------------- M0 control model
def control_matrix(m: pd.DataFrame, fr: pd.DataFrame) -> pd.DataFrame:
    """Non-astrological covariates. Anything here is *never* credited to astrology."""
    p = fr[["p1", "pd", "p2"]].clip(1e-4, 1)
    c = pd.DataFrame(index=m.index)
    c["lp1"], c["lpd"], c["lp2"] = np.log(p.p1), np.log(p["pd"]), np.log(p.p2)
    c["over25"] = m.p_over25.fillna(m.p_over25.mean())
    c["over25_missing"] = m.p_over25.isna().astype(float)
    c["overround"] = m.overround
    c["t1_home"] = fr.t1_home.astype(float)
    c["elo_diff"] = fr.elo_diff.fillna(0) / 100
    c["form_diff"] = fr.form_diff.fillna(0) / 5
    ko = m.kickoff_utc
    c["year"] = (ko.dt.year - 2020) / 5
    dummies = [pd.get_dummies(m.division, prefix="lg"),
               pd.get_dummies(ko.dt.month, prefix="mon"),
               pd.get_dummies(ko.dt.dayofweek, prefix="wd"),
               pd.get_dummies(m.local_time_uk.str[:2].astype(int), prefix="hr")]
    # draw-specific interactions so league draw rates are learned per class
    return pd.concat([c] + [d.astype(float) for d in dummies], axis=1)


class M0:
    """Multinomial logit on market log-probabilities + controls (lightly regularised)."""

    def fit(self, C: pd.DataFrame, y: np.ndarray):
        self.cols = list(C.columns)
        self.mu, self.sd = C.mean(), C.std().replace(0, 1)
        self.clf = LogisticRegression(C=1.0, max_iter=2000)
        self.clf.fit(((C - self.mu) / self.sd).to_numpy(), y)
        return self

    def predict(self, C: pd.DataFrame) -> np.ndarray:
        C = C.reindex(columns=self.cols, fill_value=0.0)
        return self.clf.predict_proba(((C - self.mu) / self.sd).to_numpy())


def market_only(fr: pd.DataFrame) -> np.ndarray:
    return fr[["p1", "pd", "p2"]].to_numpy()


# ---------------------------------------------------------------- offset softmax
def _softmax(Z):
    Z = Z - Z.max(1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(1, keepdims=True)


def shifted(logP0: np.ndarray, X: np.ndarray, w: np.ndarray, v: np.ndarray) -> np.ndarray:
    a = X @ w
    return _softmax(logP0 + np.column_stack([a, X @ v, -a]))


class OffsetSoftmax:
    """min  mean CE(y, softmax(logP0 + [Xw, Xv, -Xw])) + l1 (|w|+|v|) + l2/2 (|w|^2+|v|^2)

    Solved by FISTA with backtracking. X is standardised internally.
    """

    def __init__(self, l1=0.0, l2=0.0, max_iter=400, tol=1e-6):
        self.l1, self.l2, self.max_iter, self.tol = l1, l2, max_iter, tol

    def _prep(self, X):
        return np.clip(np.ascontiguousarray((X - self.mu) / self.sd, dtype=np.float64), -Z_CLIP, Z_CLIP)

    def fit(self, X, y, logP0, warm=None, standardise=None):
        if standardise is None:
            self.mu = X.mean(0)
            self.sd = X.std(0)
            self.sd = np.maximum(self.sd, SD_FLOOR)
        else:
            self.mu, self.sd = standardise
        Xs = self._prep(X)
        n, p = Xs.shape
        Y = onehot(y)

        def loss_grad(th):
            w, v = th[:p], th[p:]
            P = shifted(logP0, Xs, w, v)
            ll = -np.log(np.clip(P[np.arange(n), y], EPS, 1)).mean() + 0.5 * self.l2 * (th @ th)
            R = (P - Y) / n
            g = np.concatenate([Xs.T @ (R[:, 0] - R[:, 2]), Xs.T @ R[:, 1]]) + self.l2 * th
            return ll, g

        th = np.zeros(2 * p) if warm is None else warm.copy()
        z, t, L = th.copy(), 1.0, 1.0
        f_prev = np.inf
        for _ in range(self.max_iter):
            fz, gz = loss_grad(z)
            while True:
                cand = z - gz / L
                cand = np.sign(cand) * np.maximum(np.abs(cand) - self.l1 / L, 0.0)
                fc, _ = loss_grad(cand)
                d = cand - z
                if fc <= fz + gz @ d + 0.5 * L * (d @ d) + 1e-12:
                    break
                L *= 2.0
            t_new = (1 + np.sqrt(1 + 4 * t * t)) / 2
            z = cand + ((t - 1) / t_new) * (cand - th)
            th, t = cand, t_new
            obj = fc + self.l1 * np.abs(th).sum()
            if abs(f_prev - obj) < self.tol * max(1.0, abs(obj)):
                break
            f_prev = obj
            L *= 0.9
        self.theta = th
        self.w, self.v = th[:p], th[p:]
        return self

    def predict(self, X, logP0):
        return shifted(logP0, self._prep(X), self.w, self.v)

    @property
    def active(self) -> np.ndarray:
        return (np.abs(self.w) > 0) | (np.abs(self.v) > 0)


def active_count(X) -> np.ndarray:
    """Training rows where a primitive clearly departs from its typical value."""
    med = np.median(X[:: max(1, len(X) // 5000)], axis=0)
    return (np.abs(X - med) > 0.05).sum(0)


def score_vector(X, y, logP0) -> np.ndarray:
    """Per-feature score statistic at w=v=0 (gradient of the log-likelihood), for screening.

    Computed without materialising a standardised copy of X: X_s^T r = (X^T r - mu * sum r) / sd.
    """
    P = np.exp(logP0)
    R = (onehot(y) - P).astype(np.float32)
    a, b = R[:, 0] - R[:, 2], R[:, 1]
    mu = X.mean(0, dtype=np.float64)
    sd = X.std(0, dtype=np.float64)
    sd = np.maximum(sd, SD_FLOOR)
    sd[active_count(X) < MIN_ACTIVE] = np.inf
    ga = (X.T @ a - mu * a.sum()) / sd
    gb = (X.T @ b - mu * b.sum()) / sd
    return np.maximum(np.abs(ga), np.abs(gb)) / len(y)


def univariate(x, y, logP0, iters=25) -> dict:
    """1-parameter offset model eta = beta*x on the team1-vs-team2 axis. Newton-Raphson.

    Returns beta, se, z, two-sided p, and the average change in team1's win probability
    when x moves from 0 to its typical active value.
    """
    from scipy.stats import norm
    x = x.astype(float)
    b = 0.0
    for _ in range(iters):
        P = _softmax(logP0 + np.column_stack([b * x, 0 * x, -b * x]))
        r = (y == 0).astype(float) - (y == 2) - (P[:, 0] - P[:, 2])
        g = (x * r).sum()
        h = (x * x * (P[:, 0] + P[:, 2] - (P[:, 0] - P[:, 2]) ** 2)).sum()
        if h <= 0:
            break
        step = g / h
        b += step
        if abs(step) < 1e-8:
            break
    se = 1 / np.sqrt(max(h, 1e-12))
    z = b / se
    active = x != 0
    typ = np.median(np.abs(x[active])) if active.any() else 0.0
    base = np.exp(logP0[active])
    shifted_p = _softmax(logP0[active] + np.column_stack([np.full(active.sum(), b * typ), np.zeros(active.sum()),
                                                          np.full(active.sum(), -b * typ)]))
    dpp = float((shifted_p[:, 0] - base[:, 0]).mean() * 100) if active.any() else 0.0
    return {"beta": float(b), "se": float(se), "z": float(z), "p": float(2 * norm.sf(abs(z))),
            "n_active": int(active.sum()), "effect_pp": dpp}


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def holm(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p)
    n = len(p)
    order = np.argsort(p)
    adj = np.maximum.accumulate((n - np.arange(n)) * p[order])
    out = np.empty(n)
    out[order] = np.clip(adj, 0, 1)
    return out
