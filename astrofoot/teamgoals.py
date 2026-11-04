"""Team to score: which side is likelier to score at least once, the home team or the away team.

Probability. The market does not price "team to score" in our data, so it is derived from the de-vigged
1X2 probabilities: find the Poisson scoring rates (λ home, λ away) whose home-win and away-win
probabilities match the market's, then P(team scores) = 1 − e^(−λ). That raw model understates scoring
(home teams score 76% of the time, it says 73%), so it is recalibrated, σ(a + b·logit p + c·home), walk-forward
by season on the historical corpus. Out of sample every probability band lands within about a point of
the observed rate. Adding the over/under price did not improve it, so every forecast can be ranked.

Astrology. Each classical engine predicts a score, so it also says whether each team scores. Rao's and
Chokoisky's predicted scores are fixed functions of their net points (stored for every historical match),
so their calls are backtested; Frawley's is live only (see overunder.py).
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import MODELS
from .overunder import _rate

CAL_FILE = MODELS / "teamgoals.json"
ENGINES = ("rao", "chokoisky", "frawley")
DEFAULT_CAL = {"a": 0.21, "b": 1.015, "c": -0.011}
DEFAULT_BTTS = {"a": 0.33, "b": 0.885}
BTTS_WINDOW = 3


def _logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


@lru_cache(maxsize=1)
def _grid():
    from scipy.spatial import cKDTree
    from scipy.stats import poisson
    lam = np.arange(0.05, 4.51, 0.02)
    k = np.arange(15)
    pk = poisson.pmf(k[None, :], lam[:, None])
    joint = pk[:, None, :, None] * pk[None, :, None, :]
    gh, ga = np.meshgrid(k, k, indexing="ij")
    ph, pa = (joint * (gh > ga)).sum((2, 3)), (joint * (gh < ga)).sum((2, 3))
    lh, la = np.meshgrid(lam, lam, indexing="ij")
    return cKDTree(np.c_[ph.ravel(), pa.ravel()]), lh.ravel(), la.ravel()


def rates(p_home, p_away) -> tuple[np.ndarray, np.ndarray]:
    """Poisson scoring rates matching the market's home-win and away-win probabilities."""
    tree, lh, la = _grid()
    _, i = tree.query(np.c_[np.atleast_1d(p_home), np.atleast_1d(p_away)])
    return lh[i], la[i]


def load() -> dict:
    try:
        return json.loads(CAL_FILE.read_text())
    except (OSError, ValueError):
        return {"calibration": DEFAULT_CAL}


def score_probs(p_home: float, p_away: float, cal: dict | None = None) -> tuple[float, float]:
    """Calibrated P(home team scores), P(away team scores)."""
    c = (cal or load()).get("calibration", DEFAULT_CAL)
    lh, la = rates(p_home, p_away)
    raw = np.r_[1 - np.exp(-lh), 1 - np.exp(-la)]
    z = c["a"] + c["b"] * _logit(raw) + c["c"] * np.r_[1.0, 0.0]
    p = 1 / (1 + np.exp(-z))
    return float(p[0]), float(p[1])


def btts_prob(p_home: float, p_away: float, cal: dict | None = None) -> float:
    """Calibrated P(both teams score), from the same Poisson rates (recalibrated on its own)."""
    c = ((cal or load()).get("btts") or {}).get("calibration", DEFAULT_BTTS)
    lh, la = rates(p_home, p_away)
    raw = (1 - np.exp(-lh)) * (1 - np.exp(-la))
    return float(1 / (1 + np.exp(-(c["a"] + c["b"] * _logit(raw))))[0])


def _engine_goals(pred: dict | None, fav_is_home: bool) -> tuple[int, int] | None:
    if not pred or pred.get("goals_fav") is None or pred.get("goals_dog") is None:
        return None
    gf, gd = int(pred["goals_fav"]), int(pred["goals_dog"])
    return (gf, gd) if fav_is_home else (gd, gf)


def view(rec: dict, res: dict | None, cal: dict | None = None) -> dict:
    """Team-to-score fields for one sealed forecast (and its result, if settled)."""
    mk = rec["predictions"]["market"]
    fh = rec["fav_is_home"]
    p_home, p_away = (mk["fav"], mk["dog"]) if fh else (mk["dog"], mk["fav"])
    ph, pa = score_probs(p_home, p_away, cal)
    side = "home" if ph >= pa else "away"
    scores = {e: _engine_goals(rec["predictions"].get(e), fh) for e in ENGINES}
    j = 0 if side == "home" else 1
    out = {"ts_p_home": ph, "ts_p_away": pa, "ts_pick": side, "ts_pick_p": max(ph, pa),
           "ts_team": rec["home"] if side == "home" else rec["away"], "ts_engine_scores": scores,
           "ts_agree": sum(1 for s in scores.values() if s is not None and s[j] > 0), "ts_hit": None}
    pb = btts_prob(p_home, p_away, cal)
    yes = pb > 0.5
    out.update({"bt_p_yes": pb, "bt_pick": "yes" if yes else "no", "bt_pick_p": max(pb, 1 - pb),
                "bt_agree": sum(1 for s in scores.values() if s is not None and (min(s) > 0) == yes), "bt_hit": None})
    if res and res.get("goals_home") is not None:
        out["ts_hit"] = (res["goals_home"] if side == "home" else res["goals_away"]) > 0
        out["bt_hit"] = (res["goals_home"] > 0 and res["goals_away"] > 0) == yes
    return out


# ----------------------------------------------------------------------------- research
def rao_scores(win: np.ndarray, net: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(favourite scores, underdog scores) from Rao's predicted score: 1–1, 2–1, 2–0 or 3–0."""
    loser_scores = (win == 0) | (np.abs(net) <= 3)       # the winner always scores; the loser only in a close call
    return (win != -1) | loser_scores, (win != 1) | loser_scores


def chok_scores(win: np.ndarray, net: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Chokoisky: draw 1–1, otherwise w–0, so only the predicted winner scores."""
    return win != -1, win != 1


def backtest(matches: pd.DataFrame, engines: pd.DataFrame, per_day: int = 10) -> dict:
    from sklearn.linear_model import LogisticRegression

    d = pd.concat([matches[["season", "kickoff_utc", "p_home", "p_away", "fav_is_home", "goals_home",
                            "goals_away"]].reset_index(drop=True),
                   engines[["rao_win", "rao_net", "chok_win", "chok_net"]].reset_index(drop=True)], axis=1)
    d = d[d.p_home.notna() & d.goals_home.notna() & d.goals_away.notna()].reset_index(drop=True)
    lh, la = rates(d.p_home.to_numpy(), d.p_away.to_numpy())
    long = pd.DataFrame({
        "row": np.r_[d.index, d.index], "season": np.r_[d.season, d.season], "home": np.r_[np.ones(len(d)), np.zeros(len(d))],
        "p": np.r_[1 - np.exp(-lh), 1 - np.exp(-la)],
        "y": np.r_[(d.goals_home > 0), (d.goals_away > 0)].astype(float)})
    X = lambda g: np.c_[_logit(g.p.to_numpy()), g.home.to_numpy()]      # noqa: E731
    seasons = sorted(long.season.unique())
    long["pc"] = np.nan
    for s in seasons[3:]:                       # three seasons of history before the first prediction
        tr, te = long[long.season < s], long.season == s
        lr = LogisticRegression(C=1e6, max_iter=500).fit(X(tr), tr.y)
        long.loc[te, "pc"] = lr.predict_proba(X(long[te]))[:, 1]
    final = LogisticRegression(C=1e6, max_iter=500).fit(X(long), long.y)
    t = long[long.pc.notna()]
    ll = lambda q: float(-(t.y * np.log(q) + (1 - t.y) * np.log(1 - q)).mean())    # noqa: E731
    bins = pd.cut(t.pc, [0, .5, .6, .7, .8, .9, 1])
    reliability = [{"band": f"{int(100 * b.left)}–{int(100 * b.right)}%", "n": int(len(g)), "observed": float(g.y.mean()),
                    "predicted": float(g.pc.mean())} for b, g in t.groupby(bins, observed=True)]
    # per match: the likelier side, as the live page picks it
    h, a = t[t.home == 1].set_index("row"), t[t.home == 0].set_index("row")
    m = d.loc[h.index].assign(ph=h.pc, pa=a.pc.reindex(h.index), yh=h.y, ya=a.y.reindex(h.index))
    m["pick_home"] = m.ph >= m.pa
    m["pp"] = np.maximum(m.ph, m.pa)
    m["hit"] = np.where(m.pick_home, m.yh, m.ya)
    m["day"] = pd.to_datetime(m.kickoff_utc, utc=True).dt.strftime("%Y-%m-%d")
    fh = m.fav_is_home.to_numpy().astype(bool)
    calls = {}
    for name, fn, w, n in (("rao", rao_scores, "rao_win", "rao_net"), ("chokoisky", chok_scores, "chok_win", "chok_net")):
        fs, ds = fn(m[w].to_numpy(), m[n].to_numpy())
        home_s, away_s = np.where(fh, fs, ds), np.where(fh, ds, fs)
        calls[name] = (home_s, away_s)
        m[f"{name}_agree"] = np.where(m.pick_home, home_s, away_s)
    m["agree"] = m.rao_agree.astype(int) + m.chokoisky_agree.astype(int)
    top = m.sort_values(["pp", "agree"], ascending=False).groupby("day").head(per_day)
    out = {
        "calibration": {"a": float(final.intercept_[0]), "b": float(final.coef_[0, 0]), "c": float(final.coef_[0, 1])},
        "n_matches": int(len(d)), "n_test": int(len(m)), "seasons": [str(s) for s in seasons],
        "test_from": str(seasons[3]),
        "scored_rate": {"home": float((d.goals_home > 0).mean()), "away": float((d.goals_away > 0).mean())},
        "log_loss": {"raw": ll(t.p.clip(.01, .99).to_numpy()), "calibrated": ll(t.pc.to_numpy())},
        "reliability": reliability,
        "top": _rate(top.hit.to_numpy(), top.pp.to_numpy()),
        "top_home_share": float(top.pick_home.mean()),
        "top_by_agree": {str(k): _rate(g.hit.to_numpy(), g.pp.to_numpy()) for k, g in top.groupby("agree")},
        "engines": {},
    }
    for name, (home_s, away_s) in calls.items():
        # every "team scores / team fails to score" call the engine made, vs the calibrated market
        said = np.r_[home_s, away_s]
        y = np.r_[m.yh, m.ya]
        p = np.r_[m.ph, m.pa]
        hit = np.where(said, y, 1 - y)
        exp = np.where(said, p, 1 - p)
        fail = ~said
        out["engines"][name] = {**_rate(hit, exp), "blank_share": float(fail.mean()),
                                "blank_calls": _rate(hit[fail], exp[fail])}
    out["engines"]["frawley"] = {"n": 0, "note": "its goal count depends on testimony counts the history does not store"}
    out["btts"] = _btts_backtest(d, lh, la, calls, seasons, per_day)
    return out


def _btts_backtest(d, lh, la, calls, seasons, per_day) -> dict:
    """Both teams to score: walk-forward recalibration of the Poisson probability, picks and engine calls."""
    from sklearn.linear_model import LogisticRegression
    raw = (1 - np.exp(-lh)) * (1 - np.exp(-la))
    y = ((d.goals_home > 0) & (d.goals_away > 0)).to_numpy(float)
    X = _logit(raw)[:, None]
    pc = np.full(len(d), np.nan)
    # rolling window of the three previous seasons: the both-score rate drifts (50.5% in 2014/15, 55% now)
    for i, s in enumerate(seasons[3:], start=3):
        tr = ((d.season < s) & (d.season >= seasons[i - BTTS_WINDOW])).to_numpy()
        te = (d.season == s).to_numpy()
        pc[te] = LogisticRegression(C=1e6, max_iter=500).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    recent = (d.season >= seasons[-BTTS_WINDOW]).to_numpy()
    final = LogisticRegression(C=1e6, max_iter=500).fit(X[recent], y[recent])
    ok = ~np.isnan(pc)
    t = d[ok].assign(p=pc[ok], y=y[ok], raw=raw[ok])
    t["yes"] = t.p > 0.5
    t["pp"] = np.maximum(t.p, 1 - t.p)
    t["hit"] = np.where(t.yes, t.y, 1 - t.y)
    t["day"] = pd.to_datetime(t.kickoff_utc, utc=True).dt.strftime("%Y-%m-%d")
    fh = t.fav_is_home.to_numpy().astype(bool)
    eng = {}
    agree = np.zeros(len(t), int)
    for name, fn, w, n in (("rao", rao_scores, "rao_win", "rao_net"), ("chokoisky", chok_scores, "chok_win", "chok_net")):
        fs, ds = fn(t[w].to_numpy(), t[n].to_numpy())
        both = fs & ds
        agree += (both == t.yes.to_numpy()).astype(int)
        hit = np.where(both, t.y, 1 - t.y)
        exp = np.where(both, t.p, 1 - t.p)
        eng[name] = {**_rate(hit, exp), "yes_share": float(both.mean())}
    t["agree"] = agree
    top = t.sort_values(["pp", "agree"], ascending=False).groupby("day").head(per_day)
    ll = lambda q: float(-(t.y * np.log(q) + (1 - t.y) * np.log(1 - q)).mean())       # noqa: E731
    bins = pd.cut(t.p, [0, .3, .4, .5, .6, .7, 1])
    return {
        "calibration": {"a": float(final.intercept_[0]), "b": float(final.coef_[0, 0])},
        "window_seasons": BTTS_WINDOW, "rate": float(y.mean()), "recent_rate": float(y[recent].mean()), "n_test": int(len(t)),
        "log_loss": {"raw": ll(t.raw.clip(.01, .99).to_numpy()), "calibrated": ll(t.p.to_numpy()),
                     "constant": ll(np.full(len(t), y.mean()))},
        "all_picks": _rate(t.hit.to_numpy(), t.pp.to_numpy()),
        "top": _rate(top.hit.to_numpy(), top.pp.to_numpy()), "top_yes_share": float(top.yes.mean()),
        "top_by_agree": {str(k): _rate(g.hit.to_numpy(), g.pp.to_numpy()) for k, g in top.groupby("agree")},
        "reliability": [{"band": f"{int(100 * b.left)}–{int(100 * b.right)}%", "n": int(len(g)),
                         "observed": float(g.y.mean()), "predicted": float(g.p.mean())}
                        for b, g in t.groupby(bins, observed=True)],
        "engines": eng,
    }


def write(result: dict):
    CAL_FILE.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
