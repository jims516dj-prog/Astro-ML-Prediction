"""Web application: Analyze · Dataset · Match record · Emergent Codex · ML dashboard."""
from __future__ import annotations

import io
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db, foundings, live, service, venues
from ..config import DATA, MODELS, ROOT, WORK
from ..tables import JERSEY_COLOR_PLANET
from .svg import chart_wheel, orb_svg, placebo_svg, reliability_svg

HERE = Path(__file__).parent
app = FastAPI(title="Astrological Football Analyzer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
T = Jinja2Templates(directory=HERE / "templates")
T.env.globals.update(fmt_pct=lambda x, d=1: "—" if x is None else f"{100 * x:.{d}f}%",
                     fmt_num=lambda x, d=4: "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{d}f}",
                     JERSEY_COLORS=sorted(JERSEY_COLOR_PLANET))


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
def match_page(request: Request, mid: str):
    c = con()
    r = db.get_match(c, mid)
    if r is None:
        raise HTTPException(404)
    a = json.loads(r["analysis_json"])
    wheels = {z: chart_wheel(a["chart"][z], z) for z in ("tropical", "lahiri")}
    return T.TemplateResponse(request, "match.html", {
        "r": r, "a": a, "wheels": wheels, "audit": db.audit_trail(c, mid), "preds": db.predictions_for(c, mid),
        "versions": json.loads(r["versions_json"] or "[]"), "page": "dataset"})


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
                 status: str = ""):
    c = con()
    user = [dict(r) for r in db.list_matches(c)]
    for u in user:
        a = json.loads(u["analysis_json"])
        u["fav"], u["verdicts"] = a["fav"], {k: v["winner"] for k, v in a["verdicts"].items()}
        u["e4"] = a.get("engine4")
        u["consensus"] = a["synthesis"]["consensus"]
    if status:
        user = [u for u in user if u["status"] == status]
    m = imported()
    q = m
    if league:
        q = q[q.division == league]
    if season:
        q = q[q.season == season]
    if team:
        t = team.lower()
        q = q[q.home.str.lower().str.contains(t) | q.away.str.lower().str.contains(t)]
    q = q.sort_values("kickoff_utc", ascending=False)
    per = 50
    pages = max(1, math.ceil(len(q) / per))
    rows = q.iloc[(page - 1) * per: page * per]
    leagues = sorted(m.division.unique()) if len(m) else []
    seasons = sorted(m.season.unique(), reverse=True) if len(m) else []
    return T.TemplateResponse(request, "dataset.html", {
        "user": user, "rows": rows.to_dict("records"), "n": len(q), "page_no": page, "pages": pages,
        "league": league, "season": season, "team": team, "leagues": leagues, "seasons": seasons,
        "status": status, "page": "dataset"})


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


@app.post("/ml/retrain")
def retrain(stage: str = Form("codex")):
    if stage not in ("codex", "evaluate", "all"):
        raise HTTPException(400)
    cmd = [sys.executable, str(ROOT / "scripts" / "research.py"), stage]
    with open(DATA / "research.log", "a") as fh:
        subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=ROOT)
    return RedirectResponse("/ml", status_code=303)


@app.get("/live", response_class=HTMLResponse)
def live_page(request: Request):
    preds, results = live.read_predictions(), live.read_results()
    rep = live.report() if preds else None
    rows = []
    for r in sorted(preds, key=lambda r: r["kickoff_utc"], reverse=True):
        res = results.get(r["match_key"])
        out = None
        if res:
            out = ["fav", "draw", "dog"][live._outcome(r, res)]
        rows.append({**r, "result": res, "outcome": out, "verified": live.verify(r),
                     "pre_kickoff": r["committed_at"] < r["kickoff_utc"]})
    return T.TemplateResponse(request, "live.html", {"rows": rows, "rep": rep, "page": "live"})


@app.get("/api/teams")
def api_teams(q: str):
    """Founding-chart candidates for a typed team name (your saved charts first, then Wikidata)."""
    cands = foundings.search(q, con())
    for c in cands:
        ok, why = foundings.usable(c)
        c["usable"], c["why_not"] = ok, why
    return {"candidates": cands, "auto": next((c for c in cands if c["match"] in ("exact", "alias")), None),
            "table_loaded": len(foundings.table()) > 0}


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
