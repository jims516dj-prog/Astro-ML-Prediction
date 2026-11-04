"""Double chance: home or draw (1X), away or draw (X2), home or away (12).

Probability. The sum of two de-vigged 1X2 probabilities. The power-method de-vig (dataset.devig) is already
calibrated for these sums: over 107,462 historical matches, picks of the likeliest double chance won 77.6% of
the time vs 77.5% claimed, and every probability band matched, so no recalibration is applied.

Astrology. A classical engine "agrees" when the result it predicts lies inside the picked double chance
(e.g. a predicted draw agrees with 1X and X2). All three engines' winners are stored for every historical
match, so all three are backtested, Frawley included.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import MODELS
from .overunder import _rate

FILE = MODELS / "doublechance.json"
ENGINES = ("rao", "chokoisky", "frawley")
OPTIONS = ("1X", "X2", "12")
COVERS = {"1X": {"home", "draw"}, "X2": {"away", "draw"}, "12": {"home", "away"}}
LABEL = {"1X": "Home or draw", "X2": "Away or draw", "12": "Home or away"}


def load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def probs(p_home: float, p_draw: float, p_away: float) -> dict[str, float]:
    return {"1X": p_home + p_draw, "X2": p_away + p_draw, "12": p_home + p_away}


def outcome(gh: int, ga: int) -> str:
    return "home" if gh > ga else "away" if gh < ga else "draw"


def view(rec: dict, res: dict | None) -> dict:
    mk, fh = rec["predictions"]["market"], rec["fav_is_home"]
    p_home, p_away = (mk["fav"], mk["dog"]) if fh else (mk["dog"], mk["fav"])
    pr = probs(p_home, mk["draw"], p_away)
    pick = max(OPTIONS, key=pr.get)
    side = {"fav": "home" if fh else "away", "dog": "away" if fh else "home", "draw": "draw"}
    calls = {e: side.get((rec["predictions"].get(e) or {}).get("winner")) for e in ENGINES}
    out = {"dc_probs": pr, "dc_pick": pick, "dc_label": LABEL[pick], "dc_pick_p": pr[pick],
           "dc_calls": calls, "dc_agree": sum(1 for c in calls.values() if c in COVERS[pick]), "dc_hit": None}
    if res and res.get("goals_home") is not None:
        out["dc_hit"] = outcome(res["goals_home"], res["goals_away"]) in COVERS[pick]
    return out


def backtest(matches: pd.DataFrame, engines: pd.DataFrame, per_day: int = 10) -> dict:
    from .teamgoals import bands
    d = pd.concat([matches[["season", "kickoff_utc", "p_home", "p_draw", "p_away", "fav_is_home", "goals_home",
                            "goals_away"]].reset_index(drop=True),
                   engines[["rao_win", "chok_win", "fraw_win"]].reset_index(drop=True)], axis=1)
    d = d[d.p_home.notna() & d.goals_home.notna() & d.goals_away.notna()].reset_index(drop=True)
    P = pd.DataFrame({"1X": d.p_home + d.p_draw, "X2": d.p_away + d.p_draw, "12": d.p_home + d.p_away})
    pick = P.idxmax(axis=1).to_numpy()
    pp = P.max(axis=1).to_numpy()
    res = np.where(d.goals_home > d.goals_away, "home", np.where(d.goals_home < d.goals_away, "away", "draw"))
    cover = {k: np.isin(res, list(v)) for k, v in COVERS.items()}
    hit = np.select([pick == k for k in OPTIONS], [cover[k] for k in OPTIONS]).astype(float)
    fh = d.fav_is_home.to_numpy().astype(bool)
    eng, agree = {}, np.zeros(len(d), int)
    for name, col in (("rao", "rao_win"), ("chokoisky", "chok_win"), ("frawley", "fraw_win")):
        w = d[col].to_numpy()
        call = np.where(w == 0, "draw", np.where((w == 1) == fh, "home", "away"))
        call = np.where(np.isnan(w.astype(float)), "", call)
        inside = np.select([pick == k for k in OPTIONS], [np.isin(call, list(COVERS[k])) for k in OPTIONS]).astype(bool)
        agree += inside.astype(int)
        # does the pick do better when this engine agrees than the market said it would?
        eng[name] = {"agrees": _rate(hit[inside], pp[inside]), "disagrees": _rate(hit[~inside], pp[~inside]),
                     "agree_share": float(inside.mean())}
    t = d.assign(hit=hit, pp=pp, agree=agree, day=pd.to_datetime(d.kickoff_utc, utc=True).dt.strftime("%Y-%m-%d"))
    top = t.sort_values(["pp", "agree"], ascending=False).groupby("day").head(per_day)
    return {"n_matches": int(len(d)), "seasons": sorted(str(s) for s in d.season.unique()),
            "pick_share": {k: float((pick == k).mean()) for k in OPTIONS},
            "all": _rate(hit, pp), "bands": bands(hit, pp), "top": _rate(top.hit.to_numpy(), top.pp.to_numpy()),
            "by_agree": {str(k): _rate(g.hit.to_numpy(), g.pp.to_numpy()) for k, g in t.groupby("agree")},
            "engines": eng}


def write(result: dict):
    FILE.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
