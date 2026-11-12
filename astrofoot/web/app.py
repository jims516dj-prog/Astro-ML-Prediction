"""Web application: Analyze · Dataset · Match record · Emergent Codex · ML dashboard."""
from __future__ import annotations

import io
import json
import math
import subprocess
import urllib.parse
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import (db, teamnames, doublechance, form, foundings, goalmarkets, live, merged, mypicks, overunder, service, sync, teamday,
               teamgoals, venues)
from ..config import DATA, MODELS, ROOT, WORK
from ..dataset import LEAGUE_NAMES
from ..dataset import league_name as _league_name
from ..tables import JERSEY_COLOR_PLANET
from .svg import chart_wheel, orb_svg, placebo_svg, reliability_svg

HERE = Path(__file__).parent
app = FastAPI(title="Astrological Football Analyzer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
T = Jinja2Templates(directory=HERE / "templates")
T.env.filters["tn"] = teamnames.display
T.env.globals.update(fmt_pct=lambda x, d=1: "—" if x is None else f"{100 * x:.{d}f}%",
                     fmt_num=lambda x, d=4: "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{d}f}",
                     JERSEY_COLORS=sorted(JERSEY_COLOR_PLANET),
                     league_name=lambda code: _league_name(code),
                     goal_markets=lambda a: goalmarkets.from_analysis(a),
                     mypicks_market=lambda code: mypicks.MARKET_NAMES.get(code.split(":")[0], code),
                     day_label=lambda d: _day_label(d),
                     is_youth=lambda name: bool(_YOUTH_NAME.search(name or "")),
                     day_on=lambda: _DAY_ON.get())


import contextvars  # noqa: E402

from ..fixtures_espn import YOUTH_NAME as _YOUTH_NAME  # noqa: E402

_DAY_ON: contextvars.ContextVar = contextvars.ContextVar("day_on", default=True)


@app.middleware("http")
async def _day_reading_cookie(request: Request, call_next):
    """The soccer day reading can be switched off for all games (a cookie on this computer)."""
    _DAY_ON.set(request.cookies.get("dayreading") != "off")
    return await call_next(request)


@app.get("/settings/dayreading")
def day_reading_toggle(on: int = 1, back: str = "/"):
    back = back if back.startswith("/") and not back.startswith("//") else "/"
    resp = RedirectResponse(back, status_code=303)
    resp.set_cookie("dayreading", "on" if on else "off", max_age=10 * 365 * 24 * 3600, samesite="lax")
    return resp


def _day_label(d: str) -> str:
    """'Today', 'Yesterday' or 'Tomorrow' for those three dates (UTC, like the game dates); others unchanged."""
    from datetime import date as _date
    try:
        delta = (_date.fromisoformat(d) - datetime.now(timezone.utc).date()).days
    except (TypeError, ValueError):
        return d
    return {0: "Today", -1: "Yesterday", 1: "Tomorrow"}.get(delta, d)


def _gm_live(r: dict) -> dict:
    """Goal predictions for a live-ledger record (sealed odds and engine scores)."""
    mk, fh = r["predictions"]["market"], r["fav_is_home"]
    p_home, p_away = (mk["fav"], mk["dog"]) if fh else (mk["dog"], mk["fav"])
    res = r.get("result")
    result = (res["goals_home"], res["goals_away"]) if res and res.get("goals_home") is not None else None
    scores = r.get("ts_engine_scores") or {}
    return goalmarkets.markets(p_home, p_away, r.get("p_over25"), scores, result, r["home"], r["away"],
                               p_draw=mk["draw"], engine_calls=r.get("dc_calls"))


def _gm_hist(r: dict) -> dict | None:
    """Goal predictions for an imported historical match (market only: engines are not run per row)."""
    try:
        if not (r.get("p_home") == r.get("p_home") and r.get("p_away") == r.get("p_away")):
            return None
        po = r.get("p_over25")
        po = None if po is None or po != po else float(po)
        gh, ga = r.get("goals_home"), r.get("goals_away")
        result = (int(gh), int(ga)) if gh == gh and ga == ga and gh is not None else None
        return goalmarkets.markets(float(r["p_home"]), float(r["p_away"]), po, None, result, r["home"], r["away"],
                                   p_draw=float(r["p_draw"]) if r.get("p_draw") == r.get("p_draw") else None)
    except (KeyError, TypeError, ValueError):
        return None


def _json(name):
    p = MODELS / name
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache(maxsize=1)
def imported() -> pd.DataFrame:
    p = WORK / "matches.parquet"
    if not p.exists():
        return pd.DataFrame()
    m = pd.read_parquet(p)
    e = WORK / "engines_real.parquet"
    if e.exists():
        E = pd.read_parquet(e, columns=["rao_win", "chok_win", "fraw_win"])
        m = m.join(E)
    return m


def con():
    return db.connect()


# ------------------------------------------------------------------ pages
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    m = imported()
    ev, cx = _json("evaluation.json"), _json("codex.json")
    c = con()
    user = db.list_matches(c)
    led = db.ledger(c)
    stats = {"imported": len(m), "leagues": int(m.division.nunique()) if len(m) else 0,
             "seasons": f"{m.season.min()} – {m.season.max()}" if len(m) else "—",
             "user": len(user), "pending": sum(1 for r in user if r["status"] == "pending"),
             "ledger": len(led)}
    return T.TemplateResponse(request, "index.html", {"stats": stats, "ev": ev, "cx": cx, "page": "home"})


@app.get("/analyze", response_class=HTMLResponse)
def analyze_form(request: Request, historical: int = 0):
    return T.TemplateResponse(request, "analyze.html", {"historical": historical, "page": "analyze",
                                                        "now": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")})


def _f(x):
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def _i(x):
    try:
        return int(x) if x not in (None, "") else None
    except ValueError:
        return None


def _inputs_from_form(form) -> dict:
    ko = datetime.fromisoformat(form["kickoff_utc"]).replace(tzinfo=timezone.utc).isoformat()
    inp = {"team_a": form["team_a"].strip(), "team_b": form["team_b"].strip(), "kickoff_utc": ko,
           "lat": _f(form.get("lat")), "lon": _f(form.get("lon")), "venue": form.get("venue", "").strip(),
           "odds_a": _f(form["odds_a"]), "odds_d": _f(form.get("odds_d")), "odds_b": _f(form["odds_b"]),
           "home_side": form.get("home_side", "A"), "context": form.get("context", "league"),
           "time_precision": form.get("time_precision", "T2_scheduled"),
           "odds_source": form.get("odds_source", ""), "odds_type": form.get("odds_type", "other")}
    ov, un = _f(form.get("odds_over25")), _f(form.get("odds_under25"))
    p_ov = goalmarkets.p_over_from_odds(ov, un)
    if p_ov is not None:
        inp.update(odds_over25=ov, odds_under25=un, p_over25=p_ov)
    if form.get("use_captain"):
        inp["captain"] = {"a_jersey": _i(form.get("a_jersey")), "b_jersey": _i(form.get("b_jersey")),
                          "a_color": form.get("a_color") or None, "b_color": form.get("b_color") or None}
    for s in ("a", "b"):
        if form.get(f"found_{s}_date") and _f(form.get(f"found_{s}_lat")) is not None:
            inp[f"founding_{s}"] = {
                "founded_date": form[f"found_{s}_date"], "founded_time": form.get(f"found_{s}_time") or None,
                "place": form.get(f"found_{s}_place", ""), "lat": _f(form[f"found_{s}_lat"]),
                "lon": _f(form[f"found_{s}_lon"]), "source": form.get(f"found_{s}_source") or "manual",
                "kind": form.get(f"found_{s}_kind") or None, "save": bool(form.get(f"found_{s}_save"))}
    return inp


@app.post("/analyze")
async def analyze_submit(request: Request):
    form = dict(await request.form())
    inp = _inputs_from_form(form)
    dup = merged.find_duplicate(inp["team_a"], inp["team_b"], inp["kickoff_utc"], [dict(r) for r in db.list_matches(con())])
    if dup:                      # one entry per game: open the existing one instead of saving a copy
        kind, ident = dup
        return RedirectResponse(f"/live/match/{ident}?dup=1" if kind == "live" else f"/match/{ident}?dup=1",
                                status_code=303)
    if inp["lat"] is None or inp["lon"] is None:
        look = venues.lookup(inp["venue"], con())
        if look["lat"] is None:
            raise HTTPException(400, "Venue coordinates unknown — enter latitude/longitude manually.")
        inp["lat"], inp["lon"] = look["lat"], look["lon"]
        inp["loc_source"] = look["source"]
    else:
        inp["loc_source"] = form.get("loc_source") or "manual"
    a = service.analyse(inp)
    historical = form.get("mode") == "historical"
    sa, sb = _i(form.get("score_a")), _i(form.get("score_b"))
    c = con()
    if inp.get("venue"):
        db.save_venue(c, inp["venue"], inp["lat"], inp["lon"], inp["loc_source"])
    for side, team in (("a", inp["team_a"]), ("b", inp["team_b"])):
        f = inp.get(f"founding_{side}")
        if f and f.pop("save", False):
            db.save_team_chart(c, team, f["founded_date"], f["founded_time"], f["place"], f["lat"], f["lon"],
                               based_on=f["source"])
    rec = {"team_a": inp["team_a"], "team_b": inp["team_b"], "home_side": inp["home_side"], "sport": "football",
           "context": inp["context"], "kickoff_utc": inp["kickoff_utc"], "time_precision": inp["time_precision"],
           "venue": inp["venue"], "lat": inp["lat"], "lon": inp["lon"], "loc_source": inp["loc_source"],
           "odds_a": inp["odds_a"], "odds_d": inp["odds_d"], "odds_b": inp["odds_b"],
           "odds_source": inp["odds_source"], "odds_type": inp["odds_type"],
           "captain_json": json.dumps(inp.get("captain")) if inp.get("captain") else None,
           "founding_json": json.dumps({k: inp[k] for k in ("founding_a", "founding_b") if k in inp}) or None,
           "post_hoc": int(historical), "analysis_json": json.dumps(a, default=_jd), "versions_json": "[]",
           "notes": form.get("notes") or None}
    if historical and sa is not None and sb is not None:
        rec.update(score_a=sa, score_b=sb, status=form.get("status") or "completed")
    mid = db.insert_match(c, rec)
    _commit_ledger(c, mid, a, inp["kickoff_utc"])
    return RedirectResponse(f"/match/{mid}", status_code=303)


def _jd(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def _commit_ledger(c, mid, a, kickoff):
    e4 = a.get("engine4")
    version = e4["version"] if e4 else "none"
    payloads = {"market": a["market"], "synthesis": a["synthesis"]["probabilities"]}
    for k, v in a["verdicts"].items():
        payloads[k] = {"winner": v["winner"], "goals_fav": v["goals_fav"], "goals_dog": v["goals_dog"]}
    if e4:
        payloads["engine4"] = {"p_fav": e4["p_fav"], "p_draw": e4["p_draw"], "p_dog": e4["p_dog"]}
    for eng, p in payloads.items():
        db.commit_prediction(c, mid, eng, version, {"fav": a["fav"], "dog": a["dog"], **p}, kickoff)


@app.get("/match/{mid}", response_class=HTMLResponse)
def match_page(request: Request, mid: str, dup: int = 0):
    c = con()
    r = db.get_match(c, mid)
    if r is None:
        raise HTTPException(404)
    a = json.loads(r["analysis_json"])
    wheels = {z: chart_wheel(a["chart"][z], z) for z in ("tropical", "lahiri")}
    return T.TemplateResponse(request, "match.html", {
        "r": r, "a": a, "wheels": wheels, "audit": db.audit_trail(c, mid), "preds": db.predictions_for(c, mid),
        "td": _manual_teamday(dict(r), c), "td_research": teamday.research(),
        "versions": json.loads(r["versions_json"] or "[]"), "dup": dup, "page": "dataset"})


@app.post("/match/{mid}/result")
def mark_result(mid: str, score_a: int = Form(...), score_b: int = Form(...), status: str = Form("completed"),
                notes: str = Form("")):
    c = con()
    ch = {"score_a": score_a, "score_b": score_b, "status": status}
    if notes:
        ch["notes"] = notes
    db.update_match(c, mid, ch)
    return RedirectResponse(f"/match/{mid}", status_code=303)


@app.post("/match/{mid}/edit")
async def edit_match(request: Request, mid: str):
    form = dict(await request.form())
    c = con()
    r = db.get_match(c, mid)
    changes = {}
    for k in ("team_a", "team_b", "home_side", "venue", "odds_source", "odds_type", "context", "notes", "time_precision"):
        if k in form:
            changes[k] = form[k]
    for k in ("lat", "lon", "odds_a", "odds_d", "odds_b"):
        if k in form:
            changes[k] = _f(form[k])
    if form.get("kickoff_utc"):
        changes["kickoff_utc"] = datetime.fromisoformat(form["kickoff_utc"]).replace(tzinfo=timezone.utc).isoformat()
    if r["status"] != "pending" and form.get("admin_reason"):
        for k in ("score_a", "score_b"):
            if form.get(k) not in (None, ""):
                changes[k] = int(form[k])
        changes["notes"] = (form.get("notes") or "") + f" [admin correction: {form['admin_reason']}]"
    changed = db.update_match(c, mid, changes)
    if changed & db.CHART_INPUTS:
        if form.get("action") == "rerun":
            r = db.get_match(c, mid)
            inp = {"team_a": r["team_a"], "team_b": r["team_b"], "kickoff_utc": r["kickoff_utc"], "lat": r["lat"],
                   "lon": r["lon"], "odds_a": r["odds_a"], "odds_d": r["odds_d"], "odds_b": r["odds_b"],
                   "home_side": r["home_side"], "context": r["context"], "venue": r["venue"]}
            if r["captain_json"]:
                inp["captain"] = json.loads(r["captain_json"])
            a = service.analyse(inp)
            versions = json.loads(r["versions_json"] or "[]")
            versions.append({"replaced_at": db.utcnow(), "analysis": json.loads(r["analysis_json"])})
            db.update_match(c, mid, {"analysis_json": json.dumps(a, default=_jd),
                                     "versions_json": json.dumps(versions, default=_jd), "stale_analysis": 0})
            _commit_ledger(c, mid, a, r["kickoff_utc"])
        else:
            db.update_match(c, mid, {"stale_analysis": 1})
    return RedirectResponse(f"/match/{mid}", status_code=303)


@app.post("/match/{mid}/delete")
def delete_match(mid: str):
    db.update_match(con(), mid, {"deleted_at": db.utcnow()})
    return RedirectResponse("/dataset", status_code=303)


@app.get("/dataset", response_class=HTMLResponse)
def dataset_page(request: Request, league: str = "", season: str = "", team: str = "", page: int = 1,
                 status: str = "", origin: str = "", gpage: int = 1, g_from: str = "", g_to: str = "",
                 g_agree: str = "", c_from: str = "", c_to: str = "", c_agree: str = "", section: str = "men",
                 g_day: str = ""):
    section = section if section in SECTIONS else "men"
    women = section == "women"
    if women:
        origin = season = c_from = c_to = c_agree = ""
    # 1) every game we forecast: live record + games added by hand, each game once (women: the women's ledger)
    g_agree, g_ok = _agree_test(g_agree)
    games = [r for r in _filter_live(_section_games(section, include_withdrawn=status == "void"), date_from=g_from, date_to=g_to,
                                     status=status, origin=origin, league=league, team=team)
             if g_ok(r["classical_agree"])]
    if g_day:
        for r in games:
            r["td"] = _teamday(r)
        games = [r for r in games if _soc_day_ok(r["td"], g_day)]
    per = 50
    gpages = max(1, math.ceil(len(games) / per))
    gpage = min(max(gpage, 1), gpages)
    shown = games[(gpage - 1) * per: gpage * per]
    for r in shown:
        r["gm"] = _gm_live(r)
        r.setdefault("td", _teamday(r))
    # 2) the research corpus (men's football only: there is no women's historical corpus)
    m = imported().iloc[0:0] if women else imported()
    q = m
    if league:
        q = q[q.division == league]
    if season:
        q = q[q.season == season]
    if team:
        t = team.lower()
        q = q[q.home.str.lower().str.contains(t) | q.away.str.lower().str.contains(t)]
    if len(q) and (c_from or c_to):
        day = pd.to_datetime(q.kickoff_utc, utc=True).dt.strftime("%Y-%m-%d")
        q = q[((day >= c_from) if c_from else True) & ((day <= c_to) if c_to else True)]
    c_agree, c_ok = _agree_test(c_agree)
    if len(q) and c_agree:
        q = q[_corpus_agree(q).map(c_ok)]
    q = q.sort_values("kickoff_utc", ascending=False)
    pages = max(1, math.ceil(len(q) / per))
    rows = q.iloc[(page - 1) * per: page * per]
    hist = rows.to_dict("records")
    agree_n = _corpus_agree(rows) if len(rows) else []
    for r, n in zip(hist, agree_n):
        r["gm"] = _gm_hist(r)
        try:
            r["td"] = teamday.reading(r["home"], r["away"], r["kickoff_utc"], r.get("lat"), r.get("lon"), resolve=False)
        except Exception:  # noqa: BLE001
            r["td"] = None
        r["agree"] = int(n)
    leagues = sorted(set(m.division.unique()) | {r["division"] for r in games} if len(m) else
                     {r["division"] for r in games}, key=lambda c: LEAGUE_NAMES.get(c, c))
    seasons = sorted(m.season.unique(), reverse=True) if len(m) else []
    counts = {o: sum(1 for r in games if r["origin"] == o) for o in ("live", "manual")}
    keep_g = {"origin": origin, "status": status, "g_from": g_from, "g_to": g_to, "g_agree": g_agree, "g_day": g_day}
    keep_c = {"season": season, "c_from": c_from, "c_to": c_to, "c_agree": c_agree}
    shared = {"league": league, "team": team, "section": "women" if women else ""}
    qs = lambda d: "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in d.items() if v)      # noqa: E731
    return T.TemplateResponse(request, "dataset.html", {
        "games": shown, "games_n": len(games), "gpage": gpage, "gpages": gpages, "counts": counts,
        "rows": hist, "n": len(q), "page_no": page, "pages": pages,
        "league": league, "season": season, "team": team, "leagues": leagues, "seasons": seasons,
        "status": status, "origin": origin, "g_from": g_from, "g_to": g_to, "g_agree": g_agree,
        "c_from": c_from, "c_to": c_to, "c_agree": c_agree, "agree_choices": AGREE_CHOICES, "g_day": g_day,
        "soc_day": SOC_DAY,
        "keep_g": keep_g, "keep_c": keep_c, "g_qs": qs({**shared, **keep_g, **keep_c, "page": page}),
        "c_qs": qs({**shared, **keep_g, **keep_c, "gpage": gpage}), "section": section, "sections": SECTIONS,
        "page": "dataset"})


@app.get("/dataset/women.csv")
def women_csv():
    """Every women's forecast with its odds, probabilities, engine calls and result (one row per game)."""
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["kickoff_utc", "competition", "home", "away", "status", "goals_home", "goals_away", "outcome",
                "odds_home", "odds_draw", "odds_away", "odds_source", "favourite", "p_fav", "p_draw", "p_dog",
                "xg_home", "xg_away", "rao", "chokoisky", "frawley", "astrology_agrees", "void_reason", "seal_sha256",
                "committed_at"])
    for r in sorted(_women_games(include_withdrawn=True), key=lambda r: (r["kickoff_utc"], r["home"])):
        p, o, res = r["predictions"], r.get("odds") or {}, r.get("result") or {}
        xh, xa = _xg(r)
        w.writerow([r["kickoff_utc"], league_label(r["division"]), r["home"], r["away"], r["status"],
                    res.get("goals_home", ""), res.get("goals_away", ""), r.get("outcome") or "",
                    o.get("home"), o.get("draw"), o.get("away"), r.get("odds_source", ""), r.get("favourite", ""),
                    round(p["market"]["fav"], 4), round(p["market"]["draw"], 4), round(p["market"]["dog"], 4),
                    round(xh, 3), round(xa, 3), *[(p.get(e) or {}).get("winner", "") for e in ENGINE_NAMES],
                    r.get("classical_agree", ""), r.get("void_reason") or "", r.get("sha256") or "",
                    r.get("committed_at") or ""])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=women-forecasts.csv"})


def _corpus_agree(q: pd.DataFrame) -> pd.Series:
    """Per corpus match: how many classical engines picked the result the odds made most likely."""
    if not {"rao_win", "chok_win", "fraw_win"} <= set(q.columns):
        return pd.Series(0, index=q.index)
    fh = q.fav_is_home.astype(bool).to_numpy()
    probs = np.c_[np.where(fh, q.p_home, q.p_away), q.p_draw, np.where(fh, q.p_away, q.p_home)]   # fav, draw, dog
    pick = pd.Series(np.array([1, 0, -1])[probs.argmax(axis=1)], index=q.index)
    return sum((q[c] == pick).astype(int) for c in ("rao_win", "chok_win", "fraw_win"))


@app.get("/dataset/export.csv")
def export_csv():
    rows = [dict(r) for r in db.list_matches(con())]
    df = pd.DataFrame(rows).drop(columns=["analysis_json", "versions_json"], errors="ignore")
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=matches.csv"})


@app.get("/dataset/export.json")
def export_json():
    rows = [dict(r) for r in db.list_matches(con(), include_deleted=True)]
    for r in rows:
        r["analysis"] = json.loads(r.pop("analysis_json") or "null")
        r["versions"] = json.loads(r.pop("versions_json") or "[]")
    return JSONResponse(rows, headers={"Content-Disposition": "attachment; filename=matches.json"})


@app.get("/codex", response_class=HTMLResponse)
def codex_page(request: Request):
    cx, ev = _json("codex.json"), _json("evaluation.json")
    trib = pd.read_parquet(WORK / "tribunal.parquet").to_dict("records") if (WORK / "tribunal.parquet").exists() else []
    plac = placebo_svg(cx["placebo"]) if cx and cx.get("placebo") else None
    return T.TemplateResponse(request, "codex.html", {"cx": cx, "ev": ev, "trib": trib, "placebo_svg": plac,
                                                      "page": "codex"})


@app.get("/codex/rule/{key:path}", response_class=HTMLResponse)
def rule_page(request: Request, key: str):
    cx = _json("codex.json") or {}
    rule = next((r for r in cx.get("rules", []) if r["rule_key"] == key), None)
    if rule is None:
        raise HTTPException(404)
    return T.TemplateResponse(request, "rule.html", {"r": rule, "orb": orb_svg(rule.get("orb_curve")),
                                                     "page": "codex"})


@app.get("/ml", response_class=HTMLResponse)
def ml_page(request: Request):
    ev, cx, hist = _json("evaluation.json"), _json("codex.json"), _json("history.json") or []
    rel = {}
    for name in ("engine4", "m1"):
        p = WORK / f"oof_{name}.pkl"
        if p.exists():
            oof = pd.read_pickle(p)
            rel[name] = reliability_svg(np.stack(oof.P2.to_numpy()), oof.y.to_numpy())
    track = _track_record(con())
    log = (DATA / "research.log").read_text()[-4000:] if (DATA / "research.log").exists() else ""
    return T.TemplateResponse(request, "ml.html", {"ev": ev, "cx": cx, "hist": hist, "rel": rel, "track": track,
                                                   "log": log, "page": "ml"})


def _track_record(c):
    rows = [dict(r) for r in db.ledger(c) if r["committed_before_kickoff"] and r["status"] == "completed"]
    out = {}
    for r in rows:
        p = json.loads(r["payload_json"])
        fav_is_a = r["odds_a"] <= r["odds_b"]
        sf, sd = (r["score_a"], r["score_b"]) if fav_is_a else (r["score_b"], r["score_a"])
        actual = "fav" if sf > sd else "dog" if sd > sf else "draw"
        e = out.setdefault(r["engine"], {"n": 0, "hits": 0, "logloss": 0.0, "n_prob": 0})
        e["n"] += 1
        if "winner" in p:
            e["hits"] += p["winner"] == actual
        elif "p_fav" in p or "fav" in p:
            probs = {"fav": p.get("p_fav", p.get("fav")), "draw": p.get("p_draw", p.get("draw")),
                     "dog": p.get("p_dog", p.get("dog"))}
            e["hits"] += max(probs, key=lambda k: probs[k] or 0) == actual
            e["logloss"] += -math.log(max(probs[actual] or 1e-9, 1e-9))
            e["n_prob"] += 1
    for e in out.values():
        e["accuracy"] = e["hits"] / e["n"] if e["n"] else None
        e["logloss"] = e["logloss"] / e["n_prob"] if e["n_prob"] else None
    return out


AGREE_CHOICES = [("=0", "0/3 (none agree)"), ("=1", "exactly 1/3"), ("=2", "exactly 2/3"), ("=3", "3/3 (all agree)"),
                 ("1", "at least 1/3"), ("2", "at least 2/3")]


def _agree_test(agree: str):
    """'=0'..'=3': exactly that many classical engines agree; '1'..'3': at least that many; '': any."""
    if agree in ("=0", "=1", "=2", "=3"):
        return agree, (lambda n, k=int(agree[1]): n == k)
    if agree in ("1", "2", "3"):
        return agree, (lambda n, k=int(agree): n >= k)
    return "", (lambda n: True)


def _all_games(include_withdrawn: bool = False) -> list[dict]:
    """Live forecasts plus manual games (Analyze), each game once (merged.py)."""
    return merged.all_records([dict(r) for r in db.list_matches(con())], include_withdrawn=include_withdrawn)


def _teamday(r: dict) -> dict | None:
    """The day reading of a soccer game (founding dates already looked up; none are looked up while a page loads)."""
    try:
        return teamday.reading(r["home"], r["away"], r["kickoff_utc"], r.get("venue_lat"), r.get("venue_lon"), resolve=False,
                               women=str(r.get("division") or "").startswith("W:"))
    except Exception:  # noqa: BLE001
        return None


def _manual_teamday(r: dict, c=None) -> dict | None:
    """The day reading of a game analysed by hand: home and away from its home side; founding dates given on
    Analyze (your own chart or the table's) first, else looked up by name."""
    try:
        home_a = (r.get("home_side") or "A") != "B"
        home, away = (r["team_a"], r["team_b"]) if home_a else (r["team_b"], r["team_a"])
        fj = json.loads(r.get("founding_json") or "{}") or {}
        fa, fb = (fj.get("founding_a") or {}).get("founded_date"), (fj.get("founding_b") or {}).get("founded_date")
        founded = {"home": fa if home_a else fb, "away": fb if home_a else fa}
        return teamday.reading(home, away, r["kickoff_utc"], r.get("lat"), r.get("lon"), con=c, founded=founded)
    except Exception:  # noqa: BLE001
        return None


SOC_DAY = [("", "any"), ("same", "astrology and numerology favour the same team"), ("astro", "astrology favours a team"),
           ("num", "numerology favours a team"), ("score", "a team favoured to score by both")]


def _soc_day_ok(td: dict | None, want: str) -> bool:
    """Day-reading filter for soccer games (Live record, Dataset, My picks)."""
    if not want:
        return True
    if not td:
        return False
    a, n = td["favours"]["astro"], td["favours"]["num"]
    if want == "same":
        return a > 0 and a == n
    if want == "astro":
        return a > 0
    if want == "num":
        return n > 0
    if want == "score":
        return any(td[s]["score_astro"] == 1 and td[s]["score_num"] == 1 for s in ("home", "away"))
    return True


def _pick_side(p: dict, market: str) -> str | None:
    """The team a pick backs: 'home' / 'away' (None for draws and markets about both teams)."""
    if market == "summary":         # the summary's pick is one of the markets
        sub = p.get("sum_market")
        if sub == "dc":
            return {"1X": "home", "X2": "away"}.get(p.get("dc_pick"))
        return _pick_side(p, sub) if sub in ("result", "score") else None
    if market == "score":
        return p.get("ts_pick")
    if market == "result" and p.get("pick") in ("fav", "dog"):
        return "home" if (p["pick"] == "fav") == bool(p.get("fav_is_home")) else "away"
    return None


def _dayfav_ok(p: dict, market: str, want: str) -> bool:
    """Day-reading filter on Top picks: does astrology / numerology favour the pick (the team it backs)?"""
    if not want:
        return True
    if want in ("same", "score"):     # about the game, whatever the pick
        return _soc_day_ok(p.get("td"), want)
    td, side = p.get("td"), _pick_side(p, market)
    if not td or not side:
        return False
    if market == "score" or (market == "summary" and p.get("sum_market") == "score"):
        a, n = td[side]["score_astro"] == 1, td[side]["score_num"] == 1
    else:
        mine = 1 if side == "home" else 2
        a, n = td["favours"]["astro"] == mine, td["favours"]["num"] == mine
    return {"astro": a, "num": n, "both": a and n}.get(want, True)


def _filter_live(recs, date_from="", date_to="", status="", league="", team="", engine="", hit="", agree="",
                 origin=""):
    out = []
    t = team.lower().strip()
    for r in recs:
        # agreement between the overall outlook (most probable result) and the classical engines
        n = r["classical_agree"]
        if (agree == "consensus" and n < 2) or (agree == "all3" and n < 3) or (agree == "disagree" and n >= 2):
            continue
        d = r["kickoff_utc"][:10]
        if (date_from and d < date_from) or (date_to and d > date_to):
            continue
        if status and r["status"] != status:
            continue
        if origin and r.get("origin", "live") != origin:
            continue
        if league and r["division"] != league:
            continue
        if t and t not in r["home"].lower() and t not in r["away"].lower():
            continue
        if hit and engine and r["outcome"]:
            p = r["predictions"].get(engine, {})
            pick = p.get("winner") or (max(live.OUTCOMES, key=lambda k: p[k]) if "fav" in p else None)
            if (hit == "hit") != (pick == r["outcome"]):
                continue
        elif hit and engine and not r["outcome"]:
            continue
        out.append(r)
    return out


@app.get("/live", response_class=HTMLResponse)
def live_page(request: Request, date_from: str = "", date_to: str = "", status: str = "", league: str = "",
              team: str = "", engine: str = "", hit: str = "", agree: str = "", page_no: int = 1, msg: str = "",
              syncing: int = 0, origin: str = "", xg: str = "", xg_for: str = "either", section: str = "men",
              dayfav: str = ""):
    section = section if section in SECTIONS else "men"
    women = section == "women"
    recs = _section_games(section, include_withdrawn=status == "void")   # withdrawn: only under "void"
    if women:
        origin = ""
        rep = live.report(WOMEN_LEDGER) if recs else None
    else:
        rep = live.report() if any(r["origin"] == "live" for r in recs) else None
    xg_for = xg_for if xg_for in XG_FOR else "either"
    try:
        xg_min = float(xg) if xg else 0.0
    except ValueError:
        xg, xg_min = "", 0.0
    rows = [r for r in _filter_live(recs, date_from, date_to, status, league, team, engine, hit, agree, origin)
            if _xg_pass(r, xg_min, xg_for)]
    if dayfav:
        for r in rows:
            r["td"] = _teamday(r)
        rows = [r for r in rows if _soc_day_ok(r["td"], dayfav)]
    subset = live.score_picks([r for r in rows if r["pre_kickoff"]])
    per = 50
    pages = max(1, math.ceil(len(rows) / per))
    page_no = min(max(page_no, 1), pages)
    q = {"date_from": date_from, "date_to": date_to, "status": status, "league": league, "team": team,
         "engine": engine, "hit": hit, "agree": agree, "origin": origin, "xg": xg,
         "xg_for": xg_for if xg else "", "section": "women" if women else "", "dayfav": dayfav}
    shown = rows[(page_no - 1) * per: page_no * per]
    for r in shown:
        r["gm"] = _gm_live(r)
        r["td"] = _teamday(r)
    return T.TemplateResponse(request, "live.html", {
        "rows": shown, "n": len(rows), "page_no": page_no, "pages": pages,
        "q": q, "qs": "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in q.items() if v), "subset": subset, "syncing": bool(syncing) or SYNC["running"], "has_token": sync.token() is not None,
        "leagues": sorted({r["division"] for r in recs}, key=lambda c: LEAGUE_NAMES.get(c, c)), "rep": rep, "msg": msg, "xg_for_names": XG_FOR,
        "xg_steps": [t for t in form.XG_STEPS if t > 0], "section": section, "sections": SECTIONS, "soc_day": SOC_DAY,
        "page": "live"})


WOMEN_LEDGER = live.LEDGER / "women"


SECTIONS = {"men": "Men", "women": "Women"}


def _women_games(include_withdrawn: bool = False) -> list[dict]:
    """The women's forecasts (ledger/women), linked to their women's match pages."""
    out = []
    for r in live.records(WOMEN_LEDGER):
        if r.get("withdrawn") and not include_withdrawn:
            continue
        r["url"] = f"/women/match/{r['match_key']}"
        out.append(r)
    return out


def _section_games(section: str, include_withdrawn: bool = False) -> list[dict]:
    return _women_games(include_withdrawn) if section == "women" else _all_games(include_withdrawn)


def _picks_games(include_withdrawn: bool = True) -> list[dict]:
    """Men's and women's games together, for looking up the result of any saved pick."""
    return _all_games(include_withdrawn) + _women_games(include_withdrawn)


@app.get("/women", response_class=HTMLResponse)
def women_page(request: Request, day: str = "", status: str = "", league: str = "", dayfav: str = ""):
    """The women's section: its own forecasts and track record (ledger/women), never mixed with the men's."""
    recs = live.records(WOMEN_LEDGER)
    for r in recs:
        r["url"] = f"/women/match/{r['match_key']}"
        _xg_pass(r, 0.0, "either")
    live.add_summary(recs)
    days = sorted({r["kickoff_utc"][:10] for r in recs}, reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if day not in days and day != "all":
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else "all")
    rows = [r for r in recs if (day == "all" or r["kickoff_utc"][:10] == day) and (not status or r["status"] == status)
            and (not league or r["division"] == league) and (status == "void" or r["status"] != "void" or not status)]
    rows.sort(key=lambda r: (r["kickoff_utc"], r["home"]))
    for r in rows:
        r["gm"] = _gm_live(r)
        r["td"] = _teamday(r)
    rows = [r for r in rows if _soc_day_ok(r["td"], dayfav)]
    scored = [r for r in recs if r["pre_kickoff"] and r["status"] != "void"]
    return T.TemplateResponse(request, "women.html", {
        "rows": rows, "day": day, "days": days, "status": status, "league": league,
        "leagues": sorted({r["division"] for r in recs}, key=_league_name),
        "n": len(recs), "n_settled": sum(r["status"] == "settled" for r in recs),
        "score_summary": live.score_picks(scored, "summary"), "score_result": live.score_picks(scored, "result"),
        "dayfav": dayfav, "soc_day": SOC_DAY, "page": "women"})


@app.get("/women/match/{key}", response_class=HTMLResponse)
def women_match(request: Request, key: str):
    return live_match(request, key, women=True)


@app.get("/live/match/{key}", response_class=HTMLResponse)
def live_match(request: Request, key: str, dup: int = 0, women: bool = False):
    recs = live.records(WOMEN_LEDGER) if women else live.records()
    rec = next((r for r in recs if r["match_key"] == key), None)
    if rec is None:
        raise HTTPException(404)
    o = rec["odds"]
    inp = {"team_a": rec["home"], "team_b": rec["away"], "kickoff_utc": rec["kickoff_utc"],
           "lat": rec["venue_lat"], "lon": rec["venue_lon"], "odds_a": o["home"], "odds_d": o["draw"],
           "odds_b": o["away"], "home_side": "A", "context": "league", "division": rec["division"],
           "p_over25": rec.get("p_over25")}
    a = service.analyse(inp)
    # The sealed forecast is the record; the full analysis is recomputed from the same inputs and
    # flagged if today's code would decide differently (e.g. after a method fix).
    diffs = [k for k in ("rao", "chokoisky", "frawley")
             if a["verdicts"][k]["winner"] != rec["predictions"].get(k, {}).get("winner")]
    wheels = {z: chart_wheel(a["chart"][z], z) for z in ("tropical", "lahiri")}
    fc = form.analyse(rec, form.history(recs, men=not women))     # women: women's results only
    return T.TemplateResponse(request, "live_match.html", {"r": rec, "a": a, "wheels": wheels, "diffs": diffs, "dup": dup,
        "women": women, "td": _teamday(rec), "td_research": teamday.research(),
        "fc": fc, "fc_research": form.load_research(),
                                                           "team_a": rec["home"], "team_b": rec["away"],
                                                           "page": "women" if women else "live"})


# Files the GitHub jobs publish (ledger, model versions, reports). Local edits to them only block
# `git pull`, so they are reset before pulling; untracked model files are moved aside, never deleted.
GENERATED = ["ledger", "data/models", "data/work", "data/research.log", "data/selftest.log", "data/power.log",
             "FINDINGS.md"]


def _tidy_generated_files() -> str | None:
    import shutil
    st = subprocess.run(["git", "status", "--porcelain", "--", *GENERATED], cwd=ROOT, capture_output=True,
                        text=True, timeout=60).stdout.splitlines()
    modified = [ln[3:] for ln in st if ln[:2].strip() in ("M", "D", "MM", "AM")]
    untracked = [ln[3:] for ln in st if ln.startswith("??") and ln[3:].startswith("data/models/")
                 and not ln[3:].startswith("data/models/local_backup")]
    backup = None
    if untracked:
        backup = f"data/models/local_backup/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        for f in untracked:
            dst = ROOT / backup / Path(f).relative_to("data/models")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ROOT / f), str(dst))
    if modified:
        subprocess.run(["git", "checkout", "--", *modified], cwd=ROOT, capture_output=True, timeout=60)
    return backup


def _pull_and_report() -> str:
    """git pull the results/forecasts/model versions the GitHub jobs publish; summarise what arrived."""
    if not (ROOT / ".git").exists():
        return ("This folder is not a git clone: download the project again (Code → Download ZIP) "
                "to get new results.")
    from ..tennis import live as tlive
    before = live.records()
    n_res, n_fc = sum(r["status"] == "settled" for r in before), len(before)
    tb = tlive.records()
    t_res, t_fc = sum(r["status"] == "settled" for r in tb), len(tb)
    try:
        set_aside = _tidy_generated_files()
        r = subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode != 0:
            return "Update failed: " + (out[-1] if out else "git error") + " — run `git pull` in Git Bash to see details."
        after = live.records()
        new_res = sum(x["status"] == "settled" for x in after) - n_res
        new_fc = len(after) - n_fc
        ta = tlive.records()
        tennis = (f" Tennis: {sum(r['status'] == 'settled' for r in ta) - t_res} new result(s), "
                  f"{len(ta) - t_fc} new forecast(s).")
        code = any(line.strip().startswith(("astrofoot/", "scripts/")) for line in out)
        return (f"Up to date: {new_res} new result(s), {new_fc} new forecast(s)." + tennis
                + (" The app's code was also updated: restart the app to use it." if code else "")
                + (f" Local model files from an earlier refit were moved to {set_aside}." if set_aside else ""))
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Update failed: {type(e).__name__} (is Git installed?)"
    finally:
        imported.cache_clear()


BACK = {"/live", "/tennis/live"}     # pages the update buttons may return to


@app.post("/live/refresh")
def live_refresh(back: str = Form("/live")):
    """Bring in what the scheduled GitHub jobs have already published: git pull."""
    back = back if back in BACK else "/live"
    return RedirectResponse(back + "?" + urllib.parse.urlencode({"msg": _pull_and_report()}), status_code=303)


SYNC = {"running": False, "phase": "", "detail": "", "msg": ""}


def _sync_worker():
    def progress(phase, detail=""):
        SYNC.update(phase=phase, detail=detail)
    try:
        conclusion = sync.run_cycle(progress)
        progress("pulling", "Downloading the new forecasts and results")
        msg = _pull_and_report()
        if conclusion != "success":
            msg = f"GitHub's run ended with '{conclusion}' (see the repository's Actions tab). " + msg
        SYNC["msg"] = msg
    except Exception as e:  # noqa: BLE001 - shown to the user, never crashes the app
        SYNC["msg"] = f"Update now failed: {e}. " + _pull_and_report()
    finally:
        SYNC.update(running=False, phase="done")


@app.post("/live/sync")
def live_sync(back: str = Form("/live")):
    """Run the forecast/results cycle on GitHub right now, wait for it, then pull."""
    back = back if back in BACK else "/live"
    if sync.token() is None:
        return RedirectResponse(back + "?" + urllib.parse.urlencode({"msg": (
            "Update now needs a GitHub token (one-time setup, see README → 'Update now'). Meanwhile: "
            + _pull_and_report())}), status_code=303)
    if not SYNC["running"]:
        import threading
        SYNC.update(running=True, phase="starting", detail="Starting", msg="")
        threading.Thread(target=_sync_worker, daemon=True).start()
    return RedirectResponse(back + "?syncing=1", status_code=303)


@app.get("/live/sync/status")
def live_sync_status():
    return JSONResponse(SYNC)


FORM_AGREE = [("", "2/3 or 3/3"), ("=0", "0/3"), ("=1", "1/3"), ("=2", "2/3"), ("=3", "3/3")]


def _form_rows(r: dict, hist, agree: str) -> list[dict]:
    """Form checks for one game under the engines filter: '' = the team 2+ engines back; '=k' = every team exactly
    k engines call to win (with 0/3 both teams can qualify, e.g. when every engine predicts a draw)."""
    if agree in ("=0", "=1", "=2", "=3"):
        k = int(agree[1])
        return [form.analyse(r, hist, side) for side, n in form.side_counts(r).items() if n == k]
    a = form.analyse(r, hist)
    return [a] if a["qualifies"] else []


def _form_page(request: Request, day: str, agree: str, role: str, xg: str = "", section: str = "men"):
    """Top picks → Form check: a team's scoring form, for the teams the chosen number of engines back."""
    if agree == "3":                         # older links: "3/3 only"
        agree = "=3"
    agree = agree if agree in dict(FORM_AGREE) else ""
    recs = [r for r in _section_games(section) if r["status"] != "void"]
    hist = form.history(recs, men=False) if section == "women" else form.history(recs)   # women: women's results only
    days = sorted({r["kickoff_utc"][:10] for r in recs}, reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not day or day not in days:
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else today)
    try:
        xg_min = float(xg) if xg else 0.0
    except ValueError:
        xg, xg_min = "", 0.0
    want = lambda a: (not role or a["role"] == role) and a["lam_market"] >= xg_min     # noqa: E731
    rows = []
    for r in sorted((r for r in recs if r["kickoff_utc"][:10] == day), key=lambda r: (r["kickoff_utc"], r["home"])):
        rows += [{"r": r, "a": a} for a in _form_rows(r, hist, agree) if want(a)]
    # live record so far: every settled game under the same filters, all days
    done = [a for r in recs if r.get("result") and r["pre_kickoff"]
            for a in _form_rows(r, hist, agree) if want(a) and a["scored_hit"] is not None]
    n = len(done)
    so_far = {"n": n, "scored": sum(a["scored_hit"] for a in done),
              "market": sum(a["p_market"] for a in done) / n if n else None,
              "form": (sum(a["p_form"] for a in done if a["p_form"] is not None) /
                       max(1, sum(a["p_form"] is not None for a in done))) if n else None}
    research = form.load_research()
    steps = research.get("by_agree", {}).get(agree[1]) if agree else research.get("by_xg")
    return T.TemplateResponse(request, "form.html", {
        "day": day, "days": days, "rows": rows, "agree": agree, "agree_choices": FORM_AGREE,
        "agree_label": dict(FORM_AGREE)[agree], "role": role, "so_far": so_far, "xg": xg,
        "xg_steps": [t for t in form.XG_STEPS if t > 0], "xg_table": steps or [],
        "xg_hist": next((b for b in steps or [] if abs(b["min"] - xg_min) < 1e-9), None) if xg_min > 0 else None,
        "research": research, "markets": TOP_MARKETS, "market": "form", "page": "top",
        "section": section, "sections": SECTIONS, "skeep": _xg_keep("", "", "", section)})


TOP_MARKETS = [("summary", "Summary"), ("result", "Match result"), ("dc", "Double chance"), ("o15", "Over/under 1.5"),
               ("goals", "Over/under 2.5"), ("score", "Home or away goal"), ("btts", "Both teams to score"),
               ("form", "Form check")]


@app.get("/top", response_class=HTMLResponse)
def top_page(request: Request, day: str = "", market: str = "summary", agree: str = "", min_p: str = "", dayfav: str = "",
             m: list[str] = Query(default=[]), role: str = "", xg: str = "", xg_for: str = "either",
             section: str = "men"):
    section = section if section in SECTIONS else "men"
    if market == "form":
        return _form_page(request, day, agree, role, xg, section)
    xg_for = xg_for if xg_for in XG_FOR else "either"
    try:
        xg_min = float(xg) if xg else 0.0
    except ValueError:
        xg, xg_min = "", 0.0
    market = market if market in live.PICK_KEYS else "summary"
    chosen = [x for x in m if x in live.SUMMARY_MARKETS] or list(live.SUMMARY_MARKETS)
    try:
        mp = min(max(float(min_p), 0.0), 0.99) if min_p else 0.0
    except ValueError:
        mp = 0.0
    recs = _section_games(section)
    if market == "summary":
        live.add_summary(recs, chosen)
    tp = live.top_picks(recs, market=market)
    days = list(tp)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not day or day not in tp:
        day = today if today in tp else next((d for d in sorted(days) if d >= today), days[0] if days else "")
    hit_key, p_key, agree_key = live.PICK_KEYS[market]
    agree, ok_agree = _agree_test(agree)
    for ps in tp.values():
        for p in ps:
            p.setdefault("td", _teamday(p))
    keep = lambda ps: [p for p in ps if ok_agree(p.get(agree_key) or 0) and p[p_key] >= mp      # noqa: E731
                       and _xg_pass(p, xg_min, xg_for) and _dayfav_ok(p, market, dayfav)]
    picks = keep(tp.get(day, []))
    all_picks = keep([p for ps in tp.values() for p in ps])
    by_agree = {k: live.score_picks([p for p in all_picks if (p.get(agree_key) or 0) == k], market) for k in range(4)}
    edges = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0001)
    live_bands = [{"band": f"{int(100 * lo)}–{min(100, int(100 * hi))}%",
                   **live.score_picks([p for p in all_picks if lo < p[p_key] <= hi], market)}
                  for lo, hi in zip(edges[:-1], edges[1:])]
    tg = teamgoals.load()
    research = {"goals": overunder.load(), "score": tg, "btts": tg.get("btts"), "o15": tg.get("over15"),
                "dc": doublechance.load()}.get(market)
    return T.TemplateResponse(request, "top.html", {
        "day": day, "days": days, "picks": picks, "market": market, "agree": agree, "min_p": min_p,
        "xg": xg, "xg_for": xg_for, "xg_for_names": XG_FOR, "xg_steps": [t for t in form.XG_STEPS if t > 0],
        "keep": _xg_keep(xg, xg_for, "", section), "skeep": _xg_keep("", "", "", section), "dayfav": dayfav,
        "section": section, "sections": SECTIONS,
        "markets": TOP_MARKETS, "n_day_all": len(tp.get(day, [])), "chosen": chosen,
        "summary_names": dict(TOP_MARKETS),
        "summary_mix": {k: sum(1 for p in picks if p.get("sum_market") == k) for k in live.SUMMARY_MARKETS},
        "score_all": live.score_picks(all_picks, market), "score_day": live.score_picks(picks, market),
        "by_agree": by_agree, "live_bands": live_bands, "research": research,
        "ou": overunder.load() if market == "goals" else None,
        "ts": tg if market in ("score", "btts") else None,
        "guide": teamgoals.load_guide() if market == "score" else None, "page": "top"})


def _picks_view(c, games: list[dict], saved: list[dict], now_iso: str) -> list[dict]:
    """Saved picks joined with their game's result (✓/✗) and the after-kickoff flag."""
    by_key = {g["match_key"]: g for g in games}
    out = []
    for p in saved:
        g = by_key.get(p["match_key"])
        res = g.get("result") if g else None
        hit = mypicks.won(p["selection"], res["goals_home"], res["goals_away"]) if res else None
        n_agree, n_eng = mypicks.agree(p["selection"], g.get("ts_engine_scores")) if g else (None, None)
        out.append({**p, "late": p["picked_at"] >= p["kickoff_utc"], "result": res, "hit": hit,
                    "status": g["status"] if g else "unknown", "started": p["kickoff_utc"] <= now_iso,
                    "opts": mypicks.options(g) if g else [], "agree": n_agree, "n_engines": n_eng})
    return out


ENGINE_NAMES = {"rao": "Rao", "chokoisky": "Chokoisky", "frawley": "Frawley"}


def _local_kickoff(g: dict) -> tuple[str | None, str | None]:
    """Kickoff in the venue's local time (nearest-city timezone), if the venue is known."""
    from zoneinfo import ZoneInfo
    from .. import geo
    try:
        tz = geo.timezone_at(float(g["venue_lat"]), float(g["venue_lon"]))
        if tz:
            ko = datetime.fromisoformat(g["kickoff_utc"]).astimezone(ZoneInfo(tz))
            return ko.strftime("%a %d %b %Y %H:%M"), tz
    except Exception:  # noqa: BLE001 - venue tables missing or coordinates unknown
        pass
    return None, None


def _report(c, date_from: str, date_to: str, section: str = "") -> dict:
    """Everything about My picks between two dates (inclusive; empty = open), for the presentation report and
    the CSV: every pick with its game's full forecast, plus summary statistics. Nothing is filtered out."""
    section = section if section in SECTIONS else ""
    games = {g["match_key"]: g for g in _picks_games(include_withdrawn=True)}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    picks = [p for p in db.my_picks(c, section=section or None) if p.get("section") != "tennis" and (not date_from or p["day"] >= date_from) and (not date_to or p["day"] <= date_to)]
    rows = []
    for v in _picks_view(c, list(games.values()), picks, now_iso):
        g = games.get(v["match_key"])
        row = {**v, "game": g, "engines": [], "markets": [], "local": None, "tz": None}
        if g:
            row["local"], row["tz"] = _local_kickoff(g)
            calls = g.get("dc_calls") or {}
            for e, name in ENGINE_NAMES.items():
                sc = (g.get("ts_engine_scores") or {}).get(e)
                pred = g["predictions"].get(e) or {}
                row["engines"].append({"name": name, "score": sc, "call": calls.get(e) or pred.get("winner"),
                                       "confidence": pred.get("confidence"), "net": pred.get("net"),
                                       "agrees": mypicks.won(v["selection"], sc[0], sc[1]) if sc else None})
            grouped: dict[str, list] = {}
            for o in mypicks.options(g, by_probability=False):
                grouped.setdefault(o["market"], []).append(o)
            order = list(mypicks.MARKET_NAMES.values())
            row["markets"] = sorted(grouped.items(), key=lambda kv: order.index(kv[0]))
        rows.append(row)
    rows.sort(key=lambda r: (r["day"], r["slip_id"], r["kickoff_utc"], r["home"]))
    slip_list = []
    for x in db.slips(c, section=section or None):
        if x.get("section") == "tennis":
            continue
        if (date_from and x["day"] < date_from) or (date_to and x["day"] > date_to):
            continue
        mine = [r for r in rows if r["slip_id"] == x["id"]]
        if mine:
            slip_list.append({**x, **_slip_summary(mine), "rows": mine})
    scored = [r for r in rows if r["hit"] is not None and not r["late"]]
    pending = [r for r in rows if r["result"] is None and r["status"] != "void"]
    by_agree = {}
    for r in scored:
        if r["n_engines"]:
            by_agree.setdefault(f"{r['agree']}/{r['n_engines']}", []).append(r)
    by_market = {}
    for r in rows:
        by_market.setdefault(mypicks.MARKET_NAMES[r["selection"].split(":")[0]], []).append(r)
    tg = teamgoals.load()
    research = {"Over/under 2.5": overunder.load().get("all"), "Home team to score": tg.get("all"),
                "Away team to score": tg.get("all"), "Both teams to score": (tg.get("btts") or {}).get("all"),
                "Over/under 1.5": (tg.get("over15") or {}).get("all"), "Double chance": doublechance.load().get("all")}
    return {
        "rows": rows, "slips": slip_list, "generated": now_iso, "date_from": date_from, "date_to": date_to,
        "section": section, "section_name": SECTIONS.get(section, ""),
        "days": sorted({r["day"] for r in rows}),
        "summary": {"n": len(rows), "scored": mypicks.score(rows), "late": sum(r["late"] for r in rows),
                    "pending": len(pending), "void": sum(r["status"] == "void" for r in rows),
                    "all_pending_win": mypicks.all_win(pending)},
        "by_agree": {k: mypicks.score(v) for k, v in sorted(by_agree.items())},
        "by_market": {k: {**mypicks.score(v), "picks": len(v)} for k, v in by_market.items()},
        "research": research,
    }


@app.get("/mypicks/report", response_class=HTMLResponse)
def my_picks_report(request: Request, date_from: str = "", date_to: str = "", day: str = "", section: str = ""):
    if day and not (date_from or date_to):
        date_from = date_to = day
    rep = _report(con(), date_from, date_to, section)
    return T.TemplateResponse(request, "mypicks_report.html", {"r": rep, "engine_names": ENGINE_NAMES})


@app.get("/mypicks/export.csv")
def my_picks_csv(date_from: str = "", date_to: str = "", day: str = "", section: str = ""):
    import csv
    if day and not (date_from or date_to):
        date_from = date_to = day
    rep = _report(con(), date_from, date_to, section)
    cols = ["day", "section", "slip", "kickoff_utc", "kickoff_local", "venue_timezone", "league", "home", "away", "source", "seal_sha256",
            "model_version", "odds_home", "odds_draw", "odds_away", "odds_source", "favourite", "pick_market", "pick",
            "pick_probability", "astrology_agrees", "engines_with_score"]
    cols += [f"{e}_{k}" for e in ENGINE_NAMES for k in ("predicted_score_home_first", "call", "confidence", "agrees")]
    codes = ["result:home", "result:draw", "result:away", "dc:1X", "dc:X2", "dc:12", "o15:over", "o25:over",
             "hs:yes", "as:yes", "btts:yes"]
    cols += [f"p_{c.replace(':', '_')}" for c in codes]
    cols += ["picked_at", "picked_after_kickoff", "status", "goals_home", "goals_away", "pick_won", "result_source"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rep["rows"]:
        g = r["game"] or {}
        odds = g.get("odds") or {}
        probs = {o["code"]: o["p"] for o in (mypicks.options(g) if g else [])}
        line = [r["day"], SECTIONS.get(r.get("section"), "Men"), r["slip_name"], r["kickoff_utc"], r["local"] or "", r["tz"] or "", league_label(g.get("division")), r["home"],
                r["away"], g.get("origin", ""), g.get("sha256") or "", g.get("model_version") or "",
                odds.get("home"), odds.get("draw"), odds.get("away"), g.get("odds_source", ""), g.get("favourite", ""),
                mypicks.MARKET_NAMES[r["selection"].split(":")[0]], r["label"], round(r["p"], 4) if r["p"] is not None else "",
                r["agree"] if r["agree"] is not None else "", r["n_engines"] or ""]
        for e in r["engines"] or [{}] * 3:
            sc = e.get("score")
            line += [f"{sc[0]}-{sc[1]}" if sc else "", e.get("call") or "", e.get("confidence") or "",
                     "" if e.get("agrees") is None else ("yes" if e["agrees"] else "no")]
        line += [round(probs[c], 4) if c in probs else "" for c in codes]
        res = r["result"] or {}
        line += [r["picked_at"], "yes" if r["late"] else "no", r["status"], res.get("goals_home", ""),
                 res.get("goals_away", ""), "" if r["hit"] is None else ("yes" if r["hit"] else "no"),
                 res.get("source", "")]
        w.writerow(line)
    name = f"my-picks-{rep['section'] + '-' if rep['section'] else ''}{date_from or 'start'}-to-{date_to or 'latest'}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


def league_label(code: str | None) -> str:
    return _league_name(code) if code else ""


def _slip_summary(picks: list[dict]) -> dict:
    """A slip wins only if every pick on it wins; it is lost as soon as one pick loses."""
    live_picks = [p for p in picks if p["status"] != "void"]
    lost = any(p["hit"] is False for p in live_picks)
    done = bool(live_picks) and all(p["hit"] is not None for p in live_picks)
    state = "lost" if lost else "won" if done else "open" if live_picks else "empty"
    return {"n": len(picks), "state": state, "all_win": mypicks.all_win(live_picks), "score": mypicks.score(picks),
            "late": sum(p["late"] for p in picks), "void": len(picks) - len(live_picks)}


XG_FOR = {"either": "either team", "home": "home team", "away": "away team", "backed": "team backed by 2+ engines"}


def _xg(g: dict) -> tuple[float, float]:
    """Each team's expected goals implied by the match odds (the Poisson rates behind the market)."""
    mk = g["predictions"]["market"]
    p_home, p_away = (mk["fav"], mk["dog"]) if g["fav_is_home"] else (mk["dog"], mk["fav"])
    lh, la = teamgoals.rates(p_home, p_away)
    return float(lh[0]), float(la[0])


def _xg_pass(g: dict, xg_min: float, xg_for: str) -> bool:
    """Expected-goals filter (from the odds) for a game: either team, home, away, or the team backed by 2+ engines.
    Stores the figures on the record (g['xg_home'], g['xg_away']) for display."""
    if "xg_home" not in g:
        g["xg_home"], g["xg_away"] = _xg(g)
        # the engines note shown beneath each game: the team 2 or 3 of the engines back, and both counts
        side, n, _ = form.backed_side(g)
        counts = form.side_counts(g)
        g.update(eng_backed=None if side is None else g["home" if side == "home" else "away"], eng_n=n,
                 eng_home=counts["home"], eng_away=counts["away"])
    if xg_min <= 0:
        return True
    side, _, _ = form.backed_side(g)
    val = {"either": max(g["xg_home"], g["xg_away"]), "home": g["xg_home"], "away": g["xg_away"],
           "backed": None if side is None else g["xg_home" if side == "home" else "xg_away"]}[xg_for]
    return val is not None and val >= xg_min


def _xg_keep(xg: str, xg_for: str, eng: str = "", section: str = "", dayfav: str = "") -> str:
    """Query-string tail that keeps the games-list filters (and the My picks section) across slip and day changes."""
    return ("&section=women" if section == "women" else "") + (f"&dayfav={dayfav}" if dayfav in dict(SOC_DAY) and dayfav else "") + ((f"&xg={urllib.parse.quote(xg)}" if xg else "") + (f"&xg_for={xg_for}" if xg and xg_for else "")
            + (f"&eng={urllib.parse.quote(eng)}" if eng in dict(ENG_CHOICES) and eng else ""))


ENG_CHOICES = [("", "any"), ("2+", "2/3 or 3/3"), ("=3", "3/3"), ("=2", "2/3"), ("=1", "1/3"), ("=0", "0/3")]


def _eng_pass(counts: dict, eng: str) -> bool:
    """Engines filter for a game: one of its teams has that many of the 3 engines calling it to win."""
    if eng == "2+":
        return max(counts.values()) >= 2
    if eng in ("=0", "=1", "=2", "=3"):
        return int(eng[1]) in counts.values()
    return True


@app.get("/mypicks", response_class=HTMLResponse)
def my_picks_page(request: Request, day: str = "", slip: int = 0, added: int = -1, changed: int = -1,
                  removed: int = -1, dup: int = 0, xg: str = "", xg_for: str = "either", eng: str = "",
                  section: str = "men", dayfav: str = ""):
    c = con()
    section = section if section in SECTIONS else "men"
    eng = eng if eng in dict(ENG_CHOICES) else ""
    xg_for = xg_for if xg_for in XG_FOR else "either"
    try:
        xg_min = float(xg) if xg else 0.0
    except ValueError:
        xg, xg_min = "", 0.0
    games = _section_games(section)
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    days = sorted({g["kickoff_utc"][:10] for g in games}, reverse=True)
    today = now_iso[:10]
    if not day:
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else today)
    day_slips = db.slips(c, day, section)
    if not day_slips:                      # every day starts with one empty slip (per section)
        db.create_slip(c, day, section=section)
        day_slips = db.slips(c, day, section)
    active = next((x for x in day_slips if x["id"] == slip), day_slips[-1] if not slip else day_slips[0])
    day_view = _picks_view(c, games, db.my_picks(c, day, section=section), now_iso)
    for x in day_slips:
        x.update(_slip_summary([p for p in day_view if p["slip_id"] == x["id"]]))
    slip_picks = [p for p in day_view if p["slip_id"] == active["id"]]
    in_slip = {p["match_key"]: p for p in slip_picks}
    in_any: dict[str, list[str]] = {}
    for p in day_view:
        in_any.setdefault(p["match_key"], []).append(p["slip_name"])
    todays = sorted((g for g in games if g["kickoff_utc"][:10] == day and g["status"] != "void"),
                    key=lambda g: (g["kickoff_utc"], g["home"]))
    rows, hidden = [], 0
    for g in todays:
        lh, la = _xg(g)
        side, n_back, _ = form.backed_side(g)
        counts = form.side_counts(g)
        backed_xg = None if side is None else (lh if side == "home" else la)
        if not _eng_pass(counts, eng):
            hidden += 1
            continue
        td = _teamday(g)
        if not _soc_day_ok(td, dayfav):
            hidden += 1
            continue
        if xg_min > 0:
            val = {"either": max(lh, la), "home": lh, "away": la, "backed": backed_xg}[xg_for]
            if val is None or val < xg_min:
                hidden += 1
                continue
        opts = mypicks.options(g)
        pick = in_slip.get(g["match_key"])
        rows.append({"g": g, "opts": opts, "pick": pick, "chosen": pick["selection"] if pick else opts[0]["code"], "td": td,
                     "started": g["kickoff_utc"] <= now_iso, "xg_home": lh, "xg_away": la,
                     "backed": None if side is None else (g["home"] if side == "home" else g["away"]), "n_back": n_back,
                     "eng_home": counts["home"], "eng_away": counts["away"],
                     "backed_role": None if side is None else
                     ("favourite" if (side == "home") == bool(g["fav_is_home"]) else "underdog"),
                     "elsewhere": [n for n in in_any.get(g["match_key"], []) if n != active["name"]]})
    all_view = _picks_view(c, _section_games(section, include_withdrawn=True), db.my_picks(c, section=section), now_iso)
    return T.TemplateResponse(request, "mypicks.html", {
        "day": day, "days": days, "rows": rows, "slips": day_slips, "active": active,
        "day_picks": slip_picks, "slip_sum": _slip_summary(slip_picks),
        "added": added, "changed": changed, "removed": removed, "dup": dup,
        "score_day": mypicks.score(day_view), "score_all": mypicks.score(all_view),
        "n_all": len(all_view), "n_day": len(day_view), "xg": xg, "xg_for": xg_for, "xg_for_names": XG_FOR,
        "xg_steps": [t for t in form.XG_STEPS if t > 0], "hidden": hidden, "keep": _xg_keep(xg, xg_for, eng, section, dayfav),
        "eng": eng, "eng_choices": ENG_CHOICES, "section": section, "sections": SECTIONS, "dayfav": dayfav,
        "soc_day": SOC_DAY,
        "n_women": len(db.my_picks(c, section="women")),
        "page": "mypicks"})


def _pick_from(g: dict, code: str, picked_at: str) -> dict | None:
    opts = mypicks.options(g)
    # no (or an unknown) outcome sent: the most likely one, as preselected on the page
    opt = next((o for o in opts if o["code"] == code), opts[0] if opts and not code else None)
    if opt is None:
        return None
    return {"match_key": g["match_key"], "kickoff_utc": g["kickoff_utc"], "home": g["home"], "away": g["away"],
            "league": g["division"], "selection": opt["code"], "label": opt["label"], "p": opt["p"], "url": g["url"],
            "picked_at": picked_at}


def _slip_or_404(c, slip_id) -> dict:
    x = db.get_slip(c, slip_id)
    if x is None:
        raise HTTPException(404, "slip not found")
    return x


@app.post("/mypicks/slip/new")
async def my_slip_new(request: Request):
    form = await request.form()
    day = str(form.get("day", ""))
    section = str(form.get("section", "men"))
    sid = db.create_slip(con(), day, str(form.get("name", "")), section=section)
    keep = _xg_keep(str(form.get("xg", "")), str(form.get("xg_for", "")), str(form.get("eng", "")), section,
                    str(form.get("dayfav", "")))
    return RedirectResponse(f"/mypicks?day={day}&slip={sid}{keep}", status_code=303)


@app.post("/mypicks/slip/rename")
async def my_slip_rename(request: Request):
    form = await request.form()
    c = con()
    x = _slip_or_404(c, form.get("slip"))
    db.rename_slip(c, x["id"], str(form.get("name", "")))
    keep = _xg_keep(str(form.get("xg", "")), str(form.get("xg_for", "")), str(form.get("eng", "")), x["section"],
                    str(form.get("dayfav", "")))
    return RedirectResponse(f"/mypicks?day={x['day']}&slip={x['id']}{keep}", status_code=303)


@app.post("/mypicks/slip/delete")
async def my_slip_delete(request: Request):
    form = await request.form()
    c = con()
    x = _slip_or_404(c, form.get("slip"))
    db.delete_slip(c, x["id"])
    keep = _xg_keep(str(form.get("xg", "")), str(form.get("xg_for", "")), str(form.get("eng", "")), x["section"],
                    str(form.get("dayfav", "")))
    return RedirectResponse(f"/mypicks?day={x['day']}{keep}", status_code=303)


@app.post("/mypicks/add")
async def my_picks_add(request: Request):
    """Add the ticked games (with their chosen outcomes) to the active slip; its earlier picks are kept."""
    form = await request.form()
    c = con()
    x = _slip_or_404(c, form.get("slip"))
    games = {g["match_key"]: g for g in _section_games(x["section"])}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = dup = 0
    for key in form.getlist("game"):
        g = games.get(key)
        if g is None or not form.get(f"sel_{key}"):
            continue
        pick = _pick_from(g, str(form.get(f"out_{key}", "")), now_iso)
        if pick:
            if db.add_pick(c, x["id"], x["day"], pick):
                n += 1
            else:
                dup += 1
    keep = _xg_keep(str(form.get("xg", "")), str(form.get("xg_for", "")), str(form.get("eng", "")), x["section"],
                    str(form.get("dayfav", "")))
    return RedirectResponse(f"/mypicks?day={x['day']}&slip={x['id']}&added={n}&dup={dup}{keep}#mine", status_code=303)


@app.post("/mypicks/edit")
async def my_picks_edit(request: Request):
    """Change the outcome of the active slip's picks, or remove them. An unchanged pick keeps its time."""
    form = await request.form()
    c = con()
    x = _slip_or_404(c, form.get("slip"))
    games = {g["match_key"]: g for g in _section_games(x["section"])}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = removed = 0
    for p in db.my_picks(c, slip_id=x["id"]):
        pid = p["id"]
        if form.get(f"del_{pid}"):
            db.delete_pick(c, pid)
            removed += 1
            continue
        code = str(form.get(f"out_{pid}", p["selection"]))
        g = games.get(p["match_key"])
        if g is None or code == p["selection"]:
            continue
        new = _pick_from(g, code, now_iso)
        if new:
            db.update_pick(c, pid, new["selection"], new["label"], new["p"], now_iso)
            changed += 1
    keep = _xg_keep(str(form.get("xg", "")), str(form.get("xg_for", "")), str(form.get("eng", "")), x["section"],
                    str(form.get("dayfav", "")))
    return RedirectResponse(f"/mypicks?day={x['day']}&slip={x['id']}&changed={changed}&removed={removed}{keep}#mine",
                            status_code=303)


@app.get("/api/teams")
def api_teams(q: str):
    """Founding-chart candidates for a typed team name (your saved charts first, then Wikidata)."""
    cands = foundings.search(q, con())
    for c in cands:
        ok, why = foundings.usable(c)
        c["usable"], c["why_not"] = ok, why
    return {"candidates": cands, "auto": foundings.best(q, con()), "table_loaded": len(foundings.table()) > 0}


@app.get("/api/localtime")
def api_localtime(lat: float, lon: float, utc: str):
    """Live preview for the Analyze form: kickoff in the venue's local time."""
    from zoneinfo import ZoneInfo
    from .. import geo
    tz = geo.timezone_at(lat, lon)
    try:
        ko = datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, "utc must be YYYY-MM-DDTHH:MM")
    if tz is None:
        return {"timezone": None, "local": None}
    loc = ko.astimezone(ZoneInfo(tz))
    return {"timezone": tz, "local": loc.strftime("%a %d %b %Y, %H:%M"), "utc_offset": loc.strftime("%z")}


@app.get("/api/venue")
def api_venue(q: str):
    return venues.lookup(q, con())


@app.post("/api/analyse")
async def api_analyse(request: Request):
    inp = await request.json()
    return JSONResponse(json.loads(json.dumps(service.analyse(inp), default=_jd)))


# ----------------------------------------------------------------------------- tennis section
from .tennis_web import router as _tennis_router  # noqa: E402

app.include_router(_tennis_router)
from .tennis_picks import router as _tennis_picks_router  # noqa: E402

app.include_router(_tennis_picks_router)
