"""Over/under 2.5 goals: the calibrated market probability, the classical engines' calls, and their backtest.

Probability. football-data.co.uk's over/under prices are de-vigged proportionally (dataset.py), which
understates the likelier side: over 53,000 historical matches, confident over/under picks won more
often than that probability said. A one-parameter logistic recalibration, p' = σ(a + b·logit p), fitted
walk-forward by season (b ≈ 1.1), removes the gap out of sample. That calibrated probability ranks the
over/under top picks, so "expected" hit rates on the page are honest.

Astrology. Each classical engine predicts a score; its over/under call is whether that score has 3+
goals. Rao's and Chokoisky's predicted scores are fixed functions of their net points, which the
historical engine table stores, so their calls are backtested on every historical match below.
Frawley's score depends on testimony counts that the history does not store: live only, not backtested.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .config import MODELS

CAL_FILE = MODELS / "overunder.json"
ENGINES = ("rao", "chokoisky", "frawley")
DEFAULT_CAL = {"a": 0.0, "b": 1.11}


def _logit(p):
    p = np.clip(p, 0.02, 0.98)
    return np.log(p / (1 - p))


def load() -> dict:
    try:
        return json.loads(CAL_FILE.read_text())
    except (OSError, ValueError):
        return {"calibration": DEFAULT_CAL}


def calibrate(p_over_market: float | None, cal: dict | None = None) -> float | None:
    if p_over_market is None or not (0 < p_over_market < 1):
        return None
    c = (cal or load()).get("calibration", DEFAULT_CAL)
    return float(1 / (1 + math.exp(-(c["a"] + c["b"] * float(_logit(p_over_market))))))


def engine_total(pred: dict | None) -> int | None:
    if not pred or pred.get("goals_fav") is None or pred.get("goals_dog") is None:
        return None
    return int(pred["goals_fav"]) + int(pred["goals_dog"])


def view(rec: dict, res: dict | None, cal: dict | None = None) -> dict:
    """Over/under fields for one sealed forecast (and its result, if settled)."""
    p = calibrate(rec.get("p_over25"), cal)
    totals = {e: engine_total(rec["predictions"].get(e)) for e in ENGINES}
    out = {"ou_p_over": p, "ou_p_over_market": rec.get("p_over25"), "ou_engine_totals": totals,
           "ou_pick": None, "ou_pick_p": None, "ou_agree": None, "ou_goals": None, "ou_hit": None}
    if res and res.get("goals_home") is not None:
        out["ou_goals"] = int(res["goals_home"]) + int(res["goals_away"])
    if p is None:
        return out
    pick = "over" if p > 0.5 else "under"
    out.update({"ou_pick": pick, "ou_pick_p": max(p, 1 - p),
                "ou_agree": sum(1 for t in totals.values() if t is not None and (t > 2.5) == (pick == "over"))})
    if out["ou_goals"] is not None:
        out["ou_hit"] = (out["ou_goals"] > 2.5) == (pick == "over")
    return out


# ----------------------------------------------------------------------------- research
def rao_over(win: np.ndarray, net: np.ndarray) -> np.ndarray:
    """Rao's predicted score (engines/rao.py): draw 1–1; margin ≤3 → 2–1; 4–7 → 2–0; ≥8 → 3–0."""
    m = np.abs(net)
    return (win != 0) & ((m <= 3) | (m >= 8))


def chok_over(win: np.ndarray, net: np.ndarray) -> np.ndarray:
    """Chokoisky's predicted score (engines/chokoisky.py): draw 1–1, else w–0 with w = max(round(|net|/3), 1)."""
    return (win != 0) & (np.minimum(np.round(np.abs(net) / 3), 5) >= 3)


def _rate(hit: np.ndarray, exp: np.ndarray) -> dict:
    n = len(hit)
    if not n:
        return {"n": 0}
    se = float(np.sqrt((exp * (1 - exp)).sum()) / n)
    lift = float(hit.mean() - exp.mean())
    return {"n": n, "hit_rate": float(hit.mean()), "expected": float(exp.mean()), "lift": lift, "se": se,
            "z": lift / se if se else 0.0}


def backtest(matches: pd.DataFrame, engines: pd.DataFrame, per_day: int = 10) -> dict:
    """Walk-forward calibration + backtest of the over/under picks and the classical calls."""
    from sklearn.linear_model import LogisticRegression

    d = pd.concat([matches[["season", "kickoff_utc", "p_over25", "goals_home", "goals_away"]].reset_index(drop=True),
                   engines[["rao_win", "rao_net", "chok_win", "chok_net"]].reset_index(drop=True)], axis=1)
    d = d[d.p_over25.notna() & d.goals_home.notna() & d.goals_away.notna()].copy()
    d["y"] = ((d.goals_home + d.goals_away) > 2.5).astype(float)
    d["day"] = pd.to_datetime(d.kickoff_utc, utc=True).dt.strftime("%Y-%m-%d")
    seasons = sorted(d.season.unique())
    d["pc"] = np.nan
    by_season = []
    for s in seasons[1:]:
        tr, te = d[d.season < s], d.season == s
        lr = LogisticRegression(C=1e6).fit(_logit(tr.p_over25.to_numpy())[:, None], tr.y)
        d.loc[te, "pc"] = lr.predict_proba(_logit(d.loc[te, "p_over25"].to_numpy())[:, None])[:, 1]
        by_season.append({"season": s, "a": float(lr.intercept_[0]), "b": float(lr.coef_[0, 0])})
    final = LogisticRegression(C=1e6).fit(_logit(d.p_over25.to_numpy())[:, None], d.y)
    t = d[d.pc.notna()].copy()
    ll = lambda q: float(-(t.y * np.log(q) + (1 - t.y) * np.log(1 - q)).mean())     # noqa: E731
    t["pick_over"] = t.pc > 0.5
    t["pp"] = np.maximum(t.pc, 1 - t.pc)
    t["hit"] = np.where(t.pick_over, t.y, 1 - t.y)
    t["rao_over"] = rao_over(t.rao_win.to_numpy(), t.rao_net.to_numpy())
    t["chok_over"] = chok_over(t.chok_win.to_numpy(), t.chok_net.to_numpy())
    t["agree"] = (t.rao_over == t.pick_over).astype(int) + (t.chok_over == t.pick_over).astype(int)
    top = t.sort_values(["pp", "agree"], ascending=False).groupby("day").head(per_day)
    raw_pp = np.maximum(t.p_over25, 1 - t.p_over25).to_numpy()
    raw_top = t.assign(rp=raw_pp).sort_values("rp", ascending=False).groupby("day").head(per_day)
    out = {
        "calibration": {"a": float(final.intercept_[0]), "b": float(final.coef_[0, 0])},
        "walk_forward": by_season,
        "n_matches": int(len(d)), "n_test": int(len(t)), "seasons": [str(s) for s in seasons],
        "over_rate": float(d.y.mean()),
        "log_loss": {"market_raw": ll(t.p_over25.to_numpy()), "calibrated": ll(t.pc.to_numpy())},
        "top_raw": _rate(np.where(raw_top.p_over25 > 0.5, raw_top.y, 1 - raw_top.y),
                         np.maximum(raw_top.p_over25, 1 - raw_top.p_over25).to_numpy()),
        "top": _rate(top.hit.to_numpy(), top.pp.to_numpy()),
        "top_by_agree": {str(a): _rate(g.hit.to_numpy(), g.pp.to_numpy()) for a, g in top.groupby("agree")},
        "engines": {},
    }
    for name, col in (("rao", "rao_over"), ("chokoisky", "chok_over")):
        c = t[col].to_numpy()
        hit = np.where(c, t.y, 1 - t.y)
        exp = np.where(c, t.pc, 1 - t.pc)           # what the calibrated market said about the same calls
        seasons_lift = []
        for s, g in t.assign(_h=hit, _e=exp).groupby("season"):
            seasons_lift.append({"season": str(s), "lift": float(g._h.mean() - g._e.mean()), "n": int(len(g))})
        out["engines"][name] = {**_rate(hit, exp), "over_share": float(c.mean()), "by_season": seasons_lift,
                                "agree_with_market": _rate(hit[c == t.pick_over.to_numpy()],
                                                           exp[c == t.pick_over.to_numpy()])}
    out["engines"]["frawley"] = {"n": 0, "note": "its goal count depends on testimony counts the history does not store"}
    return out


def write(result: dict):
    CAL_FILE.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
