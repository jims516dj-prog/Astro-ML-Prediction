"""Tennis section of the web app: forecasts (live record), match breakdown, analyze, model (ML) and dataset."""
from __future__ import annotations

import math
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import sync
from ..tennis import DATA, ROOT, astro_num, features, model
from ..tennis import live as tlive

router = APIRouter()
TOUR = {"atp": "ATP (men)", "wta": "WTA (women)"}
RETRAIN = {"running": False, "msg": "", "log": ""}


def _T():
    from .app import T
    return T


# ----------------------------------------------------------------------------- shared state (ratings etc.)
_STATE: dict = {}


def _sources_key():
    paths = [DATA / "matches.parquet", DATA / "players.parquet", tlive.LEDGER / "recent.parquet", tlive.LEDGER / "players.json"]
    return tuple(p.stat().st_mtime if p.exists() else 0 for p in paths)


def state():
    """Ratings, form and head-to-head as of now, from the history plus the latest results (cached)."""
    key = _sources_key()
    if _STATE.get("key") != key:
        m = tlive.load_matches()
        pl = tlive.load_players()
        st = tlive.state(m, datetime.now(timezone.utc)) if len(m) else features.State()
        names = {}
        if len(m):
            for i, n in zip(pd.concat([m.p1_id, m.p2_id]), pd.concat([m.p1, m.p2])):
                names[str(i)] = n
        for r in pl.to_dict("records"):
            names.setdefault(str(r["id"]), r.get("name") or "")
        tours = {}
        if len(m):
            for i, t in zip(pd.concat([m.p1_id, m.p2_id]), pd.concat([m.tour, m.tour])):
                tours[str(i)] = t
        _STATE.update(key=key, matches=m, players=pl, pdict=features.players_dict(pl), st=st, names=names, tours=tours)
    return _STATE


# ----------------------------------------------------------------------------- explanations
SIGNED = lambda x: "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.2f}"  # noqa: E731
ASPECT_NOTE = "+1 = exact trine/conjunction (harmonious), −1 = exact square/opposition (tense), 0 = no aspect within 6°"


def _v(f, k):
    v = f.get(k)
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def explain(f: dict, m: dict) -> dict:
    """Readable factor tables (A = player 1, B = player 2) from a feature row."""
    a, b = m["p1"], m["p2"]
    num = lambda k, d=2: None if _v(f, k) is None else (int(round(float(f[k]))) if d == 0 else round(float(f[k]), d))  # noqa: E731
    stats = [
        ("Elo rating difference (A − B, all surfaces)", num("elo_diff", 0), None, "≈ +100 points ≈ 64% match chance for A"),
        ("Surface Elo difference (A − B)", num("selo_diff", 0), None, f"on {m.get('surface', 'hard')}"),
        ("Elo match chance for A (blend of the two)", num("p_elo", 3), None, "the plain rating forecast"),
        ("Form: share of the last 10 matches won", num("a_form"), num("b_form"), ""),
        ("Sets won share, last 30 sets (A − B)", num("setform_diff"), None, ""),
        ("Days since last match", num("a_rest", 1), num("b_rest", 1), "60 = 60+ days or none"),
        ("Matches in the last 14 days (A − B)", num("load_diff", 0), None, "workload"),
        ("Head-to-head wins (A − B) / meetings", num("h2h_diff", 0), num("h2h_n", 0), ""),
        ("Seed", m.get("p1_seed") or "—", m.get("p2_seed") or "—", ""),
        ("Qualifier / lucky loser", "yes" if f.get("a_q") else "no", "yes" if f.get("b_q") else "no", ""),
        ("Wildcard", "yes" if f.get("a_wc") else "no", "yes" if f.get("b_wc") else "no", ""),
        ("Age", num("a_age", 1), num("b_age", 1), ""),
        ("Height difference, inches (A − B)", num("height_diff", 1), None, ""),
        ("Left-handed", "yes" if f.get("a_left") else "no", "yes" if f.get("b_left") else "no", ""),
        ("Playing at home (venue country)", "yes" if f.get("a_home") else "no", "yes" if f.get("b_home") else "no", ""),
        ("Experience: log(matches played + 1)", num("a_n_log"), num("b_n_log"), ""),
        ("Format", "best of 5" if f.get("best_of5") else "best of 3", None,
         ("Grand Slam · " if f.get("slam") else "") + ("qualifying" if f.get("qualifying") else f"round {int(f.get('round_no') or 0)}")),
    ]
    astro = [
        ("Sun's return (1 = birthday, −1 = half a year away)", num("a_solar_return"), num("b_solar_return"), ""),
        ("Within ~10 days of the birthday", "yes" if f.get("a_birthday_window") else "no",
         "yes" if f.get("b_birthday_window") else "no", ""),
        ("Transit Jupiter → natal Sun", num("a_ju_sun"), num("b_ju_sun"), ASPECT_NOTE),
        ("Transit Saturn → natal Sun", num("a_sa_sun"), num("b_sa_sun"), ""),
        ("Transit Mars → natal Sun", num("a_ma_sun"), num("b_ma_sun"), ""),
        ("Transit Mars → natal Mars", num("a_ma_ma"), num("b_ma_ma"), ""),
        ("Transit Moon → natal Sun", num("a_mo_sun"), num("b_mo_sun"), "changes within the day"),
        ("Transit Venus → natal Venus", num("a_ve_ve"), num("b_ve_ve"), ""),
        ("Transit Jupiter → natal Moon", num("a_ju_mo"), num("b_ju_mo"), "natal Moon at noon: ±7°"),
        ("Moon's element matches natal Sun's element", "yes" if f.get("a_moon_elem_match") else "no",
         "yes" if f.get("b_moon_elem_match") else "no", ""),
        ("Natal Sun element", astro_num.ELEMENT[int(f["a_sun_elem"])] if _v(f, "a_sun_elem") is not None else "—",
         astro_num.ELEMENT[int(f["b_sun_elem"])] if _v(f, "b_sun_elem") is not None else "—", ""),
        ("Own Mars on the opponent's Sun (pressure)", num("mars_on_opp_sun_a"), num("mars_on_opp_sun_b"), "0–1, hard aspects"),
        ("Sun elements compatible (same, fire–air, earth–water)",
         "—" if _v(f, "sun_compatible") is None else ("yes" if f["sun_compatible"] else "no"), None, "shared"),
    ]
    numer = [
        ("Life path number", num("a_life_path", 0), num("b_life_path", 0), "11, 22, 33 kept as master numbers"),
        ("Personal year", num("a_personal_year", 0), num("b_personal_year", 0), ""),
        ("Personal day (match day)", num("a_personal_day", 0), num("b_personal_day", 0), ""),
        ("Expression (name) number", num("a_expression", 0), num("b_expression", 0), "Pythagorean letters"),
        ("Personal day = life path", "yes" if f.get("a_pd_is_lp") else "no", "yes" if f.get("b_pd_is_lp") else "no", ""),
        ("Personal day is a 1 or 8 (traditional 'winning' days)", "yes" if f.get("a_pd_power") else "no",
         "yes" if f.get("b_pd_power") else "no", ""),
        ("Universal day = life path", "yes" if f.get("a_ud_is_lp") else "no", "yes" if f.get("b_ud_is_lp") else "no",
         f"universal day {int(f['universal_day'])}" if _v(f, "universal_day") is not None else ""),
    ]
    return {"stats": stats, "astro": astro, "numerology": numer, "a": a, "b": b}


def _bundle_groups():
    b = model.load()
    return (b or {}).get("groups") or [], (b or {}).get("version")


# ----------------------------------------------------------------------------- pages
@router.get("/tennis", response_class=HTMLResponse)
def tennis_home(request: Request, day: str = "", tour: str = "", status: str = ""):
    from .app import _day_label  # noqa: F401
    recs = tlive.records()
    tr_all = tlive.track_record(recs)
    days = sorted({r["start_utc"][:10] for r in recs}, reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if day not in days and day != "all":
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else "all")
    rows = [r for r in recs if (day == "all" or r["start_utc"][:10] == day) and (not tour or r["tour"] == tour)
            and (not status or r["status"] == status)]
    rep = model.load_report()
    return _T().TemplateResponse(request, "tennis_home.html", {
        "rows": rows, "day": day, "days": days, "tour": tour, "status": status, "tours": TOUR, "tr": tr_all,
        "tr_day": tlive.track_record(rows), "n": len(recs), "rep": rep, "has_model": model.BUNDLE.exists(),
        "has_data": (DATA / "matches.parquet").exists(), "page": "tennis_home"})


@router.get("/tennis/match/{mid}", response_class=HTMLResponse)
def tennis_match(request: Request, mid: str):
    rec = next((r for r in tlive.records() if r["match_id"] == mid), None)
    if rec is None:
        raise HTTPException(404)
    groups, _ = _bundle_groups()
    return _T().TemplateResponse(request, "tennis_match.html", {
        "r": rec, "p": rec["p"], "x": explain(rec["features"], rec), "used": groups, "sealed": True,
        "page": "tennis_home"})


@router.get("/tennis/analyze", response_class=HTMLResponse)
def tennis_analyze(request: Request, a: str = "", b: str = "", when: str = "", surface: str = "hard", best_of: int = 3,
                   tour: str = "", round: str = "Round 1", event: str = "", a_seed: str = "", b_seed: str = "",
                   a_dob: str = "", b_dob: str = "", venue: str = ""):
    s = state()
    names = sorted({n for n in s["names"].values() if n})
    out, err = None, None
    if a and b:
        ids = {}
        by_name = {}
        for i, n in s["names"].items():
            by_name.setdefault(n.lower().strip(), []).append(i)
        for side, nm, dob in (("a", a, a_dob), ("b", b, b_dob)):
            cands = by_name.get(nm.lower().strip(), [])
            # several players can share a name: prefer the one with most matches
            pid = max(cands, key=lambda i: s["st"].n.get(i, 0)) if cands else f"manual:{nm.strip()}"
            ids[side] = pid
        pdict = dict(s["pdict"])
        for side, dob, nm in (("a", a_dob, a), ("b", b_dob, b)):
            pid = ids[side]
            if dob:
                pdict[pid] = {**pdict.get(pid, {}), "id": pid, "dob": dob, "name": nm, "full_name": nm}
            elif pid not in pdict:
                pdict[pid] = {"id": pid, "name": nm, "full_name": nm, "dob": None}
        try:
            t = datetime.fromisoformat(when).replace(tzinfo=timezone.utc) if when else datetime.now(timezone.utc)
        except ValueError:
            t, err = datetime.now(timezone.utc), "Could not read the date/time; using now."
        tr = tour or s["tours"].get(ids["a"]) or "atp"
        m = {"id": "analyze", "p1_id": ids["a"], "p2_id": ids["b"], "p1": a.strip(), "p2": b.strip(), "date": pd.Timestamp(t),
             "surface": surface if surface in ("hard", "clay", "grass") else "hard", "best_of": 5 if best_of == 5 else 3,
             "tour": tr, "round": round, "event": event, "venue": venue,
             "p1_seed": int(a_seed) if a_seed.isdigit() else None, "p2_seed": int(b_seed) if b_seed.isdigit() else None,
             "p1_country": (pdict.get(ids["a"]) or {}).get("country"), "p2_country": (pdict.get(ids["b"]) or {}).get("country")}
        f = features.row(s["st"], m, pdict)
        p = model.predict(f)
        known = {side: ids[side] in s["names"] for side in ("a", "b")}
        dob = {side: (pdict.get(ids[side]) or {}).get("dob") for side in ("a", "b")}
        out = {"m": m, "f": f, "p": p, "x": explain(f, m), "known": known, "dob": dob,
               "n": {side: s["st"].n.get(ids[side], 0) for side in ("a", "b")}}
    groups, _ = _bundle_groups()
    return _T().TemplateResponse(request, "tennis_analyze.html", {
        "names": names, "q": {"a": a, "b": b, "when": when, "surface": surface, "best_of": best_of, "tour": tour,
                              "round": round, "event": event, "a_seed": a_seed, "b_seed": b_seed, "a_dob": a_dob,
                              "b_dob": b_dob, "venue": venue},
        "out": out, "err": err, "used": groups, "has_model": model.BUNDLE.exists(), "page": "tennis_analyze"})


@router.get("/tennis/model", response_class=HTMLResponse)
def tennis_model(request: Request):
    return _T().TemplateResponse(request, "tennis_model.html", {
        "rep": model.load_report(), "names": model.HEAD_NAMES, "retrain": RETRAIN, "has_token": sync.token() is not None,
        "has_data": (DATA / "matches.parquet").exists(), "page": "tennis_model"})


def _retrain_worker():
    try:
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "tennis.py"), "train"], capture_output=True, text=True,
                           cwd=ROOT, timeout=6 * 3600)
        RETRAIN["log"] = (p.stdout + p.stderr)[-4000:]
        RETRAIN["msg"] = "Retrained: new model version saved." if p.returncode == 0 else "Retraining failed (see log)."
    except Exception as e:  # noqa: BLE001
        RETRAIN["msg"] = f"Retraining failed: {e}"
    finally:
        RETRAIN["running"] = False


@router.post("/tennis/model/retrain")
def tennis_retrain():
    if not RETRAIN["running"] and (DATA / "matches.parquet").exists():
        RETRAIN.update(running=True, msg="Retraining on this computer…", log="")
        threading.Thread(target=_retrain_worker, daemon=True).start()
    return RedirectResponse("/tennis/model", status_code=303)


@router.post("/tennis/model/github")
def tennis_github():
    tok, slug = sync.token(), sync.repo_slug()
    if not tok or not slug:
        RETRAIN["msg"] = "No GitHub token set up (see README → “Update now”)."
    else:
        try:
            sync._api("POST", f"/repos/{slug}/actions/workflows/tennis.yml/dispatches", tok, {"ref": "main", "inputs": {"cmd": "all"}})
            RETRAIN["msg"] = ("GitHub is rebuilding the tennis data and retraining (about an hour). "
                              "Then use “Get latest results” on the soccer Live record page, or git pull.")
        except Exception as e:  # noqa: BLE001
            RETRAIN["msg"] = f"Could not start the GitHub run: {e}"
    return RedirectResponse("/tennis/model", status_code=303)


@router.get("/tennis/dataset", response_class=HTMLResponse)
def tennis_dataset(request: Request, tour: str = "", surface: str = "", year: str = "", player: str = "", event: str = "",
                   page_no: int = 1):
    s = state()
    m = s["matches"]
    if len(m):
        m = m[m.completed & ~m.walkover & (m.set_winners.fillna("").str.len() > 0)]
        years = sorted({int(y) for y in m.date.dt.year.unique()}, reverse=True)
        if tour:
            m = m[m.tour == tour]
        if surface:
            m = m[m.surface == surface]
        if year.isdigit():
            m = m[m.date.dt.year == int(year)]
        if player:
            t = player.lower()
            m = m[m.p1.str.lower().str.contains(t, regex=False) | m.p2.str.lower().str.contains(t, regex=False)]
        if event:
            m = m[m.event.str.lower().str.contains(event.lower(), regex=False)]
        m = m.sort_values("date", ascending=False)
    else:
        years = []
    per = 50
    pages = max(1, math.ceil(len(m) / per))
    page_no = min(max(page_no, 1), pages)
    rows = m.iloc[(page_no - 1) * per: page_no * per].to_dict("records") if len(m) else []
    for r in rows:      # score from the winner's side
        if r.get("winner") == 2:
            r["score"] = " ".join("-".join(reversed(x.split("-"))) for x in str(r["score"]).split())
    q = {"tour": tour, "surface": surface, "year": year, "player": player, "event": event}
    by_surface = m.surface.value_counts().to_dict() if len(m) else {}
    return _T().TemplateResponse(request, "tennis_dataset.html", {
        "rows": rows, "n": len(m), "page_no": page_no, "pages": pages, "years": years, "q": q, "tours": TOUR,
        "qs": urllib.parse.urlencode({k: v for k, v in q.items() if v}), "by_surface": by_surface,
        "n_players": len(s["players"]), "n_dob": int(s["players"].dob.notna().sum()) if len(s["players"]) else 0,
        "page": "tennis_dataset"})
