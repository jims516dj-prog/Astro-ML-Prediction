"""Analyse one match end to end: charts, Engines 1-3, Engine 4, market, synthesis, guardrails."""
from __future__ import annotations

from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from . import ephem, lattice, models
from . import sky as skymod
from .config import MODELS
from .dataset import devig
from .engines import chokoisky, frawley, rao
from .engines.common import View
from .tables import BODY_NAMES, MEAN_SPEED, SIGN_NAMES

DRAWLESS_CONTEXTS = {"final", "knockout"}


def current_artifact():
    p = MODELS / "engine4_current.joblib"
    return joblib.load(p) if p.exists() else None


def _single_sky(jd, lat, lon) -> dict:
    s = skymod._chunk((np.array([jd]), np.array([lat]), np.array([lon])))
    s["jd"] = np.array([jd])
    s["lat"] = np.array([lat])
    return s


def _guardrails(rc: dict, v_trop: View, v_sid: View) -> list[str]:
    w = []
    jd = rc["jd"]
    ecl = lattice.eclipse_table()
    near = ecl[np.abs(ecl[:, 0] - jd) <= 3]
    for e in near:
        w.append(f"{'Solar' if e[1] == 0 else 'Lunar'} eclipse within ±3 days (sandhi).")
    if v_sid.lon["Su"] % 30 >= 29 or v_sid.lon["Su"] % 30 < 1:
        w.append("Solar sankranti: the Sun is changing sign (sandhi).")
    if rc.get("sun_edge_min") is not None and rc["sun_edge_min"] <= 30:
        w.append(f"Kickoff {rc['sun_edge_min']:.0f} min from sunrise/sunset at the venue (sandhi).")
    for p in ("Me", "Ve", "Ma", "Ju", "Sa"):
        if abs(v_trop.spd[p]) / MEAN_SPEED[p] < 0.08:
            w.append(f"{BODY_NAMES[p]} is stationary (within about a day of its station).")
    voc = lattice._moon_voc(rc["blon"][None, :], rc["bspd"][None, :])[0]
    if voc:
        w.append("Moon void of course (flag only; not a block for Frawley's method).")
    return w


def engine4(art, jd, lat, lon, frame_inputs: dict) -> dict | None:
    """frame_inputs: p_t1/p_d/p_t2 per frame plus control fields. Returns probs in fav terms."""
    if art is None:
        return None
    s = _single_sky(jd, lat, lon)
    X = lattice.build(s)
    frame = art["frame"]
    fi = frame_inputs[frame]
    C = pd.DataFrame([fi["controls"]])
    P0 = art["m0"][frame].predict(C)
    lp = np.log(np.clip(P0, 1e-9, 1))
    contrib = []
    if art["gate"]["engine4_in_synthesis"] or art.get("model") is not None:
        mod = art["model"]
        if mod is not None:
            x = X.reindex(columns=art["cols"], fill_value=0.0).to_numpy(np.float32)
            P = mod.predict(x, lp)
            z = mod._prep(x)[0]
            for j, c in enumerate(art["cols"]):
                if mod.w[j] or mod.v[j]:
                    a = float(mod.w[j] * z[j])
                    if abs(a) > 1e-4:
                        contrib.append({"feature": c, "desc": lattice.META.get(c, {}).get("desc", c),
                                        "team1_logodds": 2 * a, "value": float(x[0, j])})
        else:
            P = P0
    else:
        P = P0
    contrib.sort(key=lambda r: -abs(r["team1_logodds"]))
    t1_is_fav = fi["t1_is_fav"]
    p = P[0]
    pf, pdw, pd_ = (p[0], p[1], p[2]) if t1_is_fav else (p[2], p[1], p[0])
    q = P0[0]
    qf, qd, qg = (q[0], q[1], q[2]) if t1_is_fav else (q[2], q[1], q[0])
    return {"frame": frame, "p_fav": float(pf), "p_draw": float(pdw), "p_dog": float(pd_),
            "m0_fav": float(qf), "m0_draw": float(qd), "m0_dog": float(qg),
            "contributions": contrib[:8], "gate": art["gate"], "version": art["version"]}


def _controls(odds, t1_home: bool, kickoff: datetime, p_over25=None, division=None) -> dict:
    p = devig(np.array([odds]))[0]
    league = {f"lg_{division}": 1.0} if division else {}
    return {**league, "lp1": np.log(p[0]), "lpd": np.log(p[1]), "lp2": np.log(p[2]),
            "over25": p_over25 if p_over25 else 0.53, "over25_missing": 0.0 if p_over25 else 1.0,
            "overround": float((1 / np.array(odds)).sum() - 1), "t1_home": float(t1_home), "elo_diff": 0.0,
            "form_diff": 0.0, "year": (kickoff.year - 2020) / 5, f"mon_{kickoff.month}": 1.0,
            f"wd_{kickoff.weekday()}": 1.0,
            f"hr_{kickoff.astimezone(_uk()).hour}": 1.0}


def _uk():
    from zoneinfo import ZoneInfo
    return ZoneInfo("Europe/London")


def analyse(inp: dict) -> dict:
    """inp: team_a, team_b, kickoff_utc (ISO), lat, lon, odds_a, odds_d, odds_b, home_side (A/B/neutral),
    context, captain (optional dict), founding_a/b (optional {date, time_utc, lat, lon})."""
    ko = datetime.fromisoformat(inp["kickoff_utc"]).astimezone(timezone.utc)
    jd = ephem.jd_utc(ko)
    rc = ephem.raw_chart(jd, inp["lat"], inp["lon"])
    oa, ob, od = float(inp["odds_a"]), float(inp["odds_b"]), inp.get("odds_d")
    draw_possible = inp.get("context", "league") not in DRAWLESS_CONTEXTS
    fav_is_a = oa <= ob
    fav, dog = (inp["team_a"], inp["team_b"]) if fav_is_a else (inp["team_b"], inp["team_a"])
    equal_odds = abs(oa - ob) <= 0.05
    if od:
        p_a, p_d, p_b = devig(np.array([[oa, float(od), ob]]))[0]
    else:
        two = devig(np.array([[oa, ob, 1e9]]))[0]
        p_a, p_d, p_b = two[0], 0.0, two[1]
    market = {"p_fav": float(p_a if fav_is_a else p_b), "p_draw": float(p_d), "p_dog": float(p_b if fav_is_a else p_a)}

    natal = {}
    for side in ("a", "b"):
        f = inp.get(f"founding_{side}")
        if f and f.get("datetime_utc") and f.get("lat") is not None:
            njd = ephem.jd_utc(datetime.fromisoformat(f["datetime_utc"]))
            natal[side] = ephem.raw_chart(njd, float(f["lat"]), float(f["lon"]), with_hours=False)
    nat_fav = natal.get("a" if fav_is_a else "b")
    nat_dog = natal.get("b" if fav_is_a else "a")
    cap = inp.get("captain")
    if cap:
        cap = {"fav_jersey": cap.get("a_jersey") if fav_is_a else cap.get("b_jersey"),
               "dog_jersey": cap.get("b_jersey") if fav_is_a else cap.get("a_jersey"),
               "fav_color": cap.get("a_color") if fav_is_a else cap.get("b_color"),
               "dog_color": cap.get("b_color") if fav_is_a else cap.get("a_color")}
    v_rao = rao.analyse(rc, draw_possible=draw_possible, when=ko, natal_fav=nat_fav, natal_dog=nat_dog, captain=cap)
    v_cho = chokoisky.analyse(rc, fav, dog, draw_possible=draw_possible)
    v_fra = frawley.analyse(rc, draw_possible=draw_possible, extra_time=not draw_possible, equal_odds=equal_odds)

    art = current_artifact()
    e4 = None
    if art is not None and od:
        home_a = inp.get("home_side", "A") == "A"
        home_known = inp.get("home_side", "A") in ("A", "B")
        frame_inputs = {}
        for fr in ("FAV", "HOME"):
            t1_is_a = fav_is_a if fr == "FAV" else (home_a if home_known else True)
            odds = [oa, float(od), ob] if t1_is_a else [ob, float(od), oa]
            t1_home = (t1_is_a == home_a) and home_known
            frame_inputs[fr] = {"controls": _controls(odds, t1_home, ko, inp.get("p_over25"), inp.get("division")),
                                "t1_is_fav": t1_is_a == fav_is_a}
        e4 = engine4(art, jd, inp["lat"], inp["lon"], frame_inputs)

    v_trop, v_sid = View(rc, "tropical", "placidus"), View(rc, "lahiri", "whole_sign")
    verdicts = {"rao": v_rao.to_dict(), "chokoisky": v_cho.to_dict(), "frawley": v_fra.to_dict()}
    out = {
        "inputs": {k: v for k, v in inp.items()}, "fav": fav, "dog": dog, "fav_is_a": fav_is_a,
        "draw_possible": draw_possible, "equal_odds": equal_odds, "market": market, "verdicts": verdicts,
        "engine4": e4, "guardrails": _guardrails(rc, v_trop, v_sid), "chart": _chart_summary(rc),
        "kickoff_local_uk": ko.astimezone(_uk()).strftime("%Y-%m-%d %H:%M"),
    }
    out["synthesis"] = synthesise(out)
    return out


def synthesise(a: dict) -> dict:
    names = {"rao": "Rao", "chokoisky": "Chokoisky", "frawley": "Frawley"}
    calls = {k: v["winner"] for k, v in a["verdicts"].items() if v["winner"] != "disabled"}
    tally = {}
    for k, w in calls.items():
        tally.setdefault(w, []).append(k)
    top = max(tally.items(), key=lambda kv: len(kv[1])) if tally else ("fav", [])
    label = {"fav": a["fav"], "dog": a["dog"], "draw": "Draw"}
    n = len(top[1])
    if n == 3:
        consensus = f"Very strong classical consensus: {label[top[0]]}"
    elif n == 2:
        dissent = [names[k] for k in calls if k not in top[1]]
        consensus = f"Strong classical consensus: {label[top[0]]} (dissent: {', '.join(dissent)})"
    else:
        fw = calls.get("frawley", "fav")
        consensus = f"No classical consensus — leaning to Frawley by default: {label[fw]}"
    strength = {3: 40, 2: 25, 1: 10}.get(n, 10)
    for k, v in a["verdicts"].items():
        if v["confidence"] == "high" and v["winner"] == top[0]:
            strength += 10
    strength -= 15 * len(a["guardrails"])
    goals = [(v["goals_fav"], v["goals_dog"]) for v in a["verdicts"].values() if v["goals_fav"] is not None]
    lo = (min(g[0] for g in goals), min(g[1] for g in goals)) if goals else None
    hi = (max(g[0] for g in goals), max(g[1] for g in goals)) if goals else None
    e4 = a.get("engine4")
    if e4 and e4["gate"]["engine4_in_synthesis"]:
        probs = {"fav": e4["p_fav"], "draw": e4["p_draw"], "dog": e4["p_dog"]}
        source = "Engine 4 (calibrated, gate open)"
    else:
        probs = {"fav": a["market"]["p_fav"], "draw": a["market"]["p_draw"], "dog": a["market"]["p_dog"]}
        source = "Market odds (Engine 4 gate closed: no demonstrated edge)"
    best = max(probs, key=probs.get)
    return {"consensus": consensus, "classical_strength": int(max(0, min(100, strength))),
            "probabilities": probs, "probability_source": source, "most_likely": label[best],
            "most_likely_p": probs[best],
            "goal_range": f"{lo[0]}–{lo[1]} to {hi[0]}–{hi[1]} (favourite first)" if goals else None,
            "late_goal": bool(a["verdicts"]["frawley"]["features"].get("late_goal"))}


def _chart_summary(rc: dict) -> dict:
    out = {}
    for z, hs in (("tropical", "placidus"), ("lahiri", "whole_sign")):
        v = View(rc, z, hs)
        out[z] = {
            "asc": _fmt(v.asc), "mc": _fmt(v.mc), "pof": _fmt(v.pof),
            "planets": [{"p": p, "name": BODY_NAMES[p], "lon": v.lon[p], "pos": _fmt(v.lon[p]),
                         "house": v.house(p), "retro": v.retro(p)} for p in v.lon],
            "cusps": [float(c) for c in v.cusps],
        }
    return out


def _fmt(x: float) -> str:
    s = int(x // 30)
    d = x % 30
    return f"{int(d):02d}°{int(round((d % 1) * 60)) % 60:02d}′ {SIGN_NAMES[s]}"
