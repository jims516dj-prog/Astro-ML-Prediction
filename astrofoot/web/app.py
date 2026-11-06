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

from .. import db, doublechance, foundings, goalmarkets, live, merged, mypicks, overunder, service, sync, teamgoals, venues
from ..config import DATA, MODELS, ROOT, WORK
from ..dataset import LEAGUE_NAMES
from ..tables import JERSEY_COLOR_PLANET
from .svg import chart_wheel, orb_svg, placebo_svg, reliability_svg

HERE = Path(__file__).parent
app = FastAPI(title="Astrological Football Analyzer")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
T = Jinja2Templates(directory=HERE / "templates")
T.env.globals.update(fmt_pct=lambda x, d=1: "—" if x is None else f"{100 * x:.{d}f}%",
                     fmt_num=lambda x, d=4: "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{d}f}",
                     JERSEY_COLORS=sorted(JERSEY_COLOR_PLANET),
                     league_name=lambda code: LEAGUE_NAMES.get(code, code),
                     goal_markets=lambda a: goalmarkets.from_analysis(a),
                     mypicks_market=lambda code: mypicks.MARKET_NAMES.get(code.split(":")[0], code))


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
                 g_agree: str = "", c_from: str = "", c_to: str = "", c_agree: str = ""):
    # 1) every game we forecast: live record + games added by hand, each game once
    g_agree, g_ok = _agree_test(g_agree)
    games = [r for r in _filter_live(_all_games(include_withdrawn=status == "void"), date_from=g_from, date_to=g_to,
                                     status=status, origin=origin, league=league, team=team)
             if g_ok(r["classical_agree"])]
    per = 50
    gpages = max(1, math.ceil(len(games) / per))
    gpage = min(max(gpage, 1), gpages)
    shown = games[(gpage - 1) * per: gpage * per]
    for r in shown:
        r["gm"] = _gm_live(r)
    # 2) the research corpus
    m = imported()
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
        r["agree"] = int(n)
    leagues = sorted(set(m.division.unique()) | {r["division"] for r in games} if len(m) else
                     {r["division"] for r in games}, key=lambda c: LEAGUE_NAMES.get(c, c))
    seasons = sorted(m.season.unique(), reverse=True) if len(m) else []
    counts = {o: sum(1 for r in games if r["origin"] == o) for o in ("live", "manual")}
    keep_g = {"origin": origin, "status": status, "g_from": g_from, "g_to": g_to, "g_agree": g_agree}
    keep_c = {"season": season, "c_from": c_from, "c_to": c_to, "c_agree": c_agree}
    shared = {"league": league, "team": team}
    qs = lambda d: "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in d.items() if v)      # noqa: E731
    return T.TemplateResponse(request, "dataset.html", {
        "games": shown, "games_n": len(games), "gpage": gpage, "gpages": gpages, "counts": counts,
        "rows": hist, "n": len(q), "page_no": page, "pages": pages,
        "league": league, "season": season, "team": team, "leagues": leagues, "seasons": seasons,
        "status": status, "origin": origin, "g_from": g_from, "g_to": g_to, "g_agree": g_agree,
        "c_from": c_from, "c_to": c_to, "c_agree": c_agree, "agree_choices": AGREE_CHOICES,
        "keep_g": keep_g, "keep_c": keep_c, "g_qs": qs({**shared, **keep_g, **keep_c, "page": page}),
        "c_qs": qs({**shared, **keep_g, **keep_c, "gpage": gpage}), "page": "dataset"})


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
              syncing: int = 0, origin: str = ""):
    recs = _all_games(include_withdrawn=status == "void")   # withdrawn duplicates: only under "void"
    rep = live.report() if any(r["origin"] == "live" for r in recs) else None
    rows = _filter_live(recs, date_from, date_to, status, league, team, engine, hit, agree, origin)
    subset = live.score_picks([r for r in rows if r["pre_kickoff"]])
    per = 50
    pages = max(1, math.ceil(len(rows) / per))
    page_no = min(max(page_no, 1), pages)
    q = {"date_from": date_from, "date_to": date_to, "status": status, "league": league, "team": team,
         "engine": engine, "hit": hit, "agree": agree, "origin": origin}
    shown = rows[(page_no - 1) * per: page_no * per]
    for r in shown:
        r["gm"] = _gm_live(r)
    return T.TemplateResponse(request, "live.html", {
        "rows": shown, "n": len(rows), "page_no": page_no, "pages": pages,
        "q": q, "qs": "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in q.items() if v), "subset": subset, "syncing": bool(syncing) or SYNC["running"], "has_token": sync.token() is not None,
        "leagues": sorted({r["division"] for r in recs}, key=lambda c: LEAGUE_NAMES.get(c, c)), "rep": rep, "msg": msg, "page": "live"})


@app.get("/live/match/{key}", response_class=HTMLResponse)
def live_match(request: Request, key: str, dup: int = 0):
    rec = next((r for r in live.records() if r["match_key"] == key), None)
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
    return T.TemplateResponse(request, "live_match.html", {"r": rec, "a": a, "wheels": wheels, "diffs": diffs, "dup": dup,
                                                           "team_a": rec["home"], "team_b": rec["away"],
                                                           "page": "live"})


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
    before = live.records()
    n_res, n_fc = sum(r["status"] == "settled" for r in before), len(before)
    try:
        set_aside = _tidy_generated_files()
        r = subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode != 0:
            return "Update failed: " + (out[-1] if out else "git error") + " — run `git pull` in Git Bash to see details."
        after = live.records()
        new_res = sum(x["status"] == "settled" for x in after) - n_res
        new_fc = len(after) - n_fc
        code = any(line.strip().startswith(("astrofoot/", "scripts/")) for line in out)
        return (f"Up to date: {new_res} new result(s), {new_fc} new forecast(s)."
                + (" The app's code was also updated: restart the app to use it." if code else "")
                + (f" Local model files from an earlier refit were moved to {set_aside}." if set_aside else ""))
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Update failed: {type(e).__name__} (is Git installed?)"
    finally:
        imported.cache_clear()


@app.post("/live/refresh")
def live_refresh():
    """Bring in what the scheduled GitHub jobs have already published: git pull."""
    return RedirectResponse("/live?" + urllib.parse.urlencode({"msg": _pull_and_report()}), status_code=303)


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
def live_sync():
    """Run the forecast/results cycle on GitHub right now, wait for it, then pull."""
    if sync.token() is None:
        return RedirectResponse("/live?" + urllib.parse.urlencode({"msg": (
            "Update now needs a GitHub token (one-time setup, see README → 'Update now'). Meanwhile: "
            + _pull_and_report())}), status_code=303)
    if not SYNC["running"]:
        import threading
        SYNC.update(running=True, phase="starting", detail="Starting", msg="")
        threading.Thread(target=_sync_worker, daemon=True).start()
    return RedirectResponse("/live?syncing=1", status_code=303)


@app.get("/live/sync/status")
def live_sync_status():
    return JSONResponse(SYNC)


TOP_MARKETS = [("summary", "Summary"), ("result", "Match result"), ("dc", "Double chance"), ("o15", "Over/under 1.5"),
               ("goals", "Over/under 2.5"), ("score", "Home or away goal"), ("btts", "Both teams to score")]


@app.get("/top", response_class=HTMLResponse)
def top_page(request: Request, day: str = "", market: str = "summary", agree: str = "", min_p: str = "",
             m: list[str] = Query(default=[])):
    market = market if market in live.PICK_KEYS else "summary"
    chosen = [x for x in m if x in live.SUMMARY_MARKETS] or list(live.SUMMARY_MARKETS)
    try:
        mp = min(max(float(min_p), 0.0), 0.99) if min_p else 0.0
    except ValueError:
        mp = 0.0
    recs = _all_games()
    if market == "summary":
        live.add_summary(recs, chosen)
    tp = live.top_picks(recs, market=market)
    days = list(tp)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not day or day not in tp:
        day = today if today in tp else next((d for d in sorted(days) if d >= today), days[0] if days else "")
    hit_key, p_key, agree_key = live.PICK_KEYS[market]
    agree, ok_agree = _agree_test(agree)
    keep = lambda ps: [p for p in ps if ok_agree(p.get(agree_key) or 0) and p[p_key] >= mp]   # noqa: E731
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
        "markets": TOP_MARKETS, "n_day_all": len(tp.get(day, [])), "chosen": chosen,
        "summary_names": dict(TOP_MARKETS),
        "summary_mix": {k: sum(1 for p in picks if p.get("sum_market") == k) for k in live.SUMMARY_MARKETS},
        "score_all": live.score_picks(all_picks, market), "score_day": live.score_picks(picks, market),
        "by_agree": by_agree, "live_bands": live_bands, "research": research,
        "ou": overunder.load() if market == "goals" else None,
        "ts": tg if market in ("score", "btts") else None, "page": "top"})


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


def _report(c, date_from: str, date_to: str) -> dict:
    """Everything about My picks between two dates (inclusive; empty = open), for the presentation report and
    the CSV: every pick with its game's full forecast, plus summary statistics. Nothing is filtered out."""
    games = {g["match_key"]: g for g in _all_games(include_withdrawn=True)}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    picks = [p for p in db.my_picks(c) if (not date_from or p["day"] >= date_from) and (not date_to or p["day"] <= date_to)]
    view = {v["match_key"]: v for v in _picks_view(c, list(games.values()), picks, now_iso)}
    rows = []
    for p in picks:
        v, g = view[p["match_key"]], games.get(p["match_key"])
        row = {**v, "game": g, "engines": [], "markets": [], "local": None, "tz": None}
        if g:
            row["local"], row["tz"] = _local_kickoff(g)
            calls = g.get("dc_calls") or {}
            for e, name in ENGINE_NAMES.items():
                sc = (g.get("ts_engine_scores") or {}).get(e)
                pred = g["predictions"].get(e) or {}
                row["engines"].append({"name": name, "score": sc, "call": calls.get(e) or pred.get("winner"),
                                       "confidence": pred.get("confidence"), "net": pred.get("net"),
                                       "agrees": mypicks.won(p["selection"], sc[0], sc[1]) if sc else None})
            grouped: dict[str, list] = {}
            for o in mypicks.options(g, by_probability=False):
                grouped.setdefault(o["market"], []).append(o)
            order = list(mypicks.MARKET_NAMES.values())
            row["markets"] = sorted(grouped.items(), key=lambda kv: order.index(kv[0]))
        rows.append(row)
    rows.sort(key=lambda r: (r["kickoff_utc"], r["home"]))
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
        "rows": rows, "generated": now_iso, "date_from": date_from, "date_to": date_to,
        "days": sorted({r["day"] for r in rows}),
        "summary": {"n": len(rows), "scored": mypicks.score(rows), "late": sum(r["late"] for r in rows),
                    "pending": len(pending), "void": sum(r["status"] == "void" for r in rows),
                    "all_pending_win": mypicks.all_win(pending)},
        "by_agree": {k: mypicks.score(v) for k, v in sorted(by_agree.items())},
        "by_market": {k: {**mypicks.score(v), "picks": len(v)} for k, v in by_market.items()},
        "research": research,
    }


@app.get("/mypicks/report", response_class=HTMLResponse)
def my_picks_report(request: Request, date_from: str = "", date_to: str = "", day: str = ""):
    if day and not (date_from or date_to):
        date_from = date_to = day
    rep = _report(con(), date_from, date_to)
    return T.TemplateResponse(request, "mypicks_report.html", {"r": rep, "engine_names": ENGINE_NAMES})


@app.get("/mypicks/export.csv")
def my_picks_csv(date_from: str = "", date_to: str = "", day: str = ""):
    import csv
    if day and not (date_from or date_to):
        date_from = date_to = day
    rep = _report(con(), date_from, date_to)
    cols = ["day", "kickoff_utc", "kickoff_local", "venue_timezone", "league", "home", "away", "source", "seal_sha256",
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
        line = [r["day"], r["kickoff_utc"], r["local"] or "", r["tz"] or "", league_label(g.get("division")), r["home"],
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
    name = f"my-picks-{date_from or 'start'}-to-{date_to or 'latest'}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


def league_label(code: str | None) -> str:
    return LEAGUE_NAMES.get(code, code or "")


@app.get("/mypicks", response_class=HTMLResponse)
def my_picks_page(request: Request, day: str = "", added: int = -1, changed: int = -1, removed: int = -1):
    c = con()
    games = _all_games()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    days = sorted({g["kickoff_utc"][:10] for g in games}, reverse=True)
    today = now_iso[:10]
    if not day:
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else today)
    mine = {p["match_key"]: p for p in db.my_picks(c, day)}
    todays = sorted((g for g in games if g["kickoff_utc"][:10] == day and g["status"] != "void"),
                    key=lambda g: (g["kickoff_utc"], g["home"]))
    rows = []
    for g in todays:
        opts = mypicks.options(g)
        pick = mine.get(g["match_key"])
        rows.append({"g": g, "opts": opts, "pick": pick, "chosen": pick["selection"] if pick else opts[0]["code"],
                     "started": g["kickoff_utc"] <= now_iso})
    day_picks = _picks_view(c, games, db.my_picks(c, day), now_iso)
    all_picks = _picks_view(c, games, db.my_picks(c), now_iso)
    return T.TemplateResponse(request, "mypicks.html", {
        "day": day, "days": days, "rows": rows, "day_picks": day_picks,
        "added": added, "changed": changed, "removed": removed,
        "score_day": mypicks.score(day_picks), "score_all": mypicks.score(all_picks),
        "all_win": mypicks.all_win(day_picks), "n_all": len(all_picks), "page": "mypicks"})


def _pick_from(g: dict, code: str, picked_at: str) -> dict | None:
    opts = mypicks.options(g)
    # no (or an unknown) outcome sent: the most likely one, as preselected on the page
    opt = next((o for o in opts if o["code"] == code), opts[0] if opts and not code else None)
    if opt is None:
        return None
    return {"match_key": g["match_key"], "kickoff_utc": g["kickoff_utc"], "home": g["home"], "away": g["away"],
            "league": g["division"], "selection": opt["code"], "label": opt["label"], "p": opt["p"], "url": g["url"],
            "picked_at": picked_at}


@app.post("/mypicks/add")
async def my_picks_add(request: Request):
    """Add the ticked games (with their chosen outcomes) to the day's picks; earlier picks are kept."""
    form = await request.form()
    day = str(form.get("day", ""))
    c = con()
    games = {g["match_key"]: g for g in _all_games()}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    have = {p["match_key"] for p in db.my_picks(c)}
    n = 0
    for key in form.getlist("game"):
        g = games.get(key)
        if g is None or not form.get(f"sel_{key}") or key in have:
            continue
        pick = _pick_from(g, str(form.get(f"out_{key}", "")), now_iso)
        if pick:
            db.upsert_my_pick(c, day, pick)
            n += 1
    return RedirectResponse(f"/mypicks?day={day}&added={n}#mine", status_code=303)


@app.post("/mypicks/edit")
async def my_picks_edit(request: Request):
    """Change the outcome of saved picks, or remove them. An unchanged pick keeps its original time."""
    form = await request.form()
    day = str(form.get("day", ""))
    c = con()
    games = {g["match_key"]: g for g in _all_games()}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = removed = 0
    for p in db.my_picks(c, day):
        key = p["match_key"]
        if form.get(f"del_{key}"):
            db.delete_my_pick(c, key)
            removed += 1
            continue
        code = str(form.get(f"out_{key}", p["selection"]))
        g = games.get(key)
        if g is None or code == p["selection"]:
            continue
        pick = _pick_from(g, code, now_iso)
        if pick:
            db.upsert_my_pick(c, day, pick)
            changed += 1
    return RedirectResponse(f"/mypicks?day={day}&changed={changed}&removed={removed}#mine", status_code=303)


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
