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
    return {"stats": stats, "a": a, "b": b}


def day_of(rec: dict) -> dict:
    """The date-only astrology / numerology comparison: sealed with the forecast, or worked out now (it depends
    only on the two dates of birth and the match date) for forecasts sealed before it existed."""
    if rec.get("day"):
        return rec["day"]
    m = {"p1_id": rec["p1_id"], "p2_id": rec["p2_id"], "p1": rec["p1"], "p2": rec["p2"], "date": rec["start_utc"]}
    return tlive.day_compare(m, state()["pdict"])


def edge_pts(logit: float | None) -> float | None:
    """A learned log-odds edge as percentage points on an even set (50% → 50% + this)."""
    if logit is None:
        return None
    return 100 * (1 / (1 + math.exp(-logit)) - 0.5)


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
    for r in rows:
        r["dayv"] = day_of(r)
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
        "r": rec, "p": rec["p"], "x": explain(rec["features"], rec), "used": groups, "sealed": True, "day": day_of(rec),
        "edge_pts": edge_pts, "page": "tennis_home"})


@router.get("/tennis/analyze", response_class=HTMLResponse)
def tennis_analyze(request: Request, a: str = "", b: str = "", when: str = "", surface: str = "hard", best_of: int = 3,
                   tour: str = "", round: str = "Round 1", event: str = "", a_seed: str = "", b_seed: str = "",
                   a_dob: str = "", b_dob: str = "", venue: str = "", a_odds: str = "", b_odds: str = ""):
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
        try:
            odds = (float(a_odds), float(b_odds)) if a_odds and b_odds else None
            if odds and min(odds) <= 1.0:
                odds, err = None, "Odds must be decimal and above 1.00 (e.g. 1.45 and 2.80)."
        except ValueError:
            odds, err = None, "Could not read the odds; use decimal odds such as 1.45."
        p = model.predict(f, odds=odds)
        known = {side: ids[side] in s["names"] for side in ("a", "b")}
        dob = {side: (pdict.get(ids[side]) or {}).get("dob") for side in ("a", "b")}
        out = {"m": m, "f": f, "p": p, "x": explain(f, m), "known": known, "dob": dob,
               "day": tlive.day_compare(m, pdict),
               "n": {side: s["st"].n.get(ids[side], 0) for side in ("a", "b")}}
    groups, _ = _bundle_groups()
    return _T().TemplateResponse(request, "tennis_analyze.html", {
        "names": names, "q": {"a": a, "b": b, "when": when, "surface": surface, "best_of": best_of, "tour": tour,
                              "round": round, "event": event, "a_seed": a_seed, "b_seed": b_seed, "a_dob": a_dob,
                              "b_dob": b_dob, "venue": venue, "a_odds": a_odds, "b_odds": b_odds},
        "out": out, "err": err, "used": groups, "edge_pts": edge_pts, "has_model": model.BUNDLE.exists(), "page": "tennis_analyze"})


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


# ----------------------------------------------------------------------------- top picks
TOP_MARKETS = [("set", "Sets"), ("first", "First set"), ("match", "Match"), ("one_set", "Wins at least one set"),
               ("dog_set", "Underdog wins a set")]
AGREE = [("", "any"), ("yes", "favours the pick"), ("no", "does not favour it")]


def pick_of(r: dict, market: str) -> dict:
    """The pick of one forecast in one market: which player, its expected probability and, once played, the result."""
    e = r["e"]
    side = {"set": r["set_pick"], "first": r["first_pick"], "match": r["match_pick"], "one_set": r["one_pick"],
            "dog_set": r["dog"]}[market]
    key = {"set": "set", "first": "first", "match": "match", "one_set": "one_set", "dog_set": "one_set"}[market]
    p = e[("a_" if side == 1 else "b_") + key]
    hit = n = None
    if r["status"] == "settled":
        sw = r["result"]["set_winners"]
        if market == "set":
            hit, n = sw.count(str(side)), len(sw)
        elif market == "first":
            hit, n = int(sw[:1] == str(side)), 1
        elif market == "match":
            hit, n = int(r["result"]["winner"] == side), 1
        else:
            hit, n = int(str(side) in sw), 1
    d = r["dayv"]
    return {"side": side, "player": r["p1"] if side == 1 else r["p2"], "p": p, "hit": hit, "n": n,
            "astro": d["astro"]["favours"] == side, "astro_any": d["astro"]["favours"] != 0,
            "num": d["num"]["favours"] == side, "num_any": d["num"]["favours"] != 0}


@router.get("/tennis/top", response_class=HTMLResponse)
def tennis_top(request: Request, market: str = "set", day: str = "", tour: str = "", min_p: str = "", astro: str = "",
               num: str = "", odds: str = ""):
    market = market if market in dict(TOP_MARKETS) else "set"
    recs = [r for r in tlive.records() if r["status"] != "void"]
    for r in recs:
        r["dayv"] = day_of(r)
        r["pick"] = pick_of(r, market)
    try:
        mp = float(min_p) if min_p else 0.0
    except ValueError:
        mp = 0.0

    def keep(r):
        k = r["pick"]
        return ((not tour or r["tour"] == tour) and k["p"] >= mp
                and (not astro or (astro == "yes") == k["astro"]) and (not num or (num == "yes") == k["num"])
                and (not odds or bool(r.get("odds"))))

    days = sorted({r["start_utc"][:10] for r in recs}, reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if day not in days and day != "all":
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else "all")
    pool = [r for r in recs if keep(r)]
    rows = sorted((r for r in pool if day == "all" or r["start_utc"][:10] == day), key=lambda r: -r["pick"]["p"])

    def tally(rs):
        done = [r for r in rs if r["pick"]["hit"] is not None and r["pre_kickoff"]]
        n = sum(r["pick"]["n"] for r in done)
        hits = sum(r["pick"]["hit"] for r in done)
        exp = sum(r["pick"]["p"] * r["pick"]["n"] for r in done)
        return {"n": n, "hits": hits, "rate": hits / n if n else None, "expected": exp / n if n else None, "matches": len(done)}

    by_view = {label: tally([r for r in pool if f(r["pick"])]) for label, f in (
        ("Astrology favours the pick", lambda k: k["astro"]), ("Astrology favours the other player", lambda k: k["astro_any"] and not k["astro"]),
        ("Numerology favours the pick", lambda k: k["num"]), ("Numerology favours the other player", lambda k: k["num_any"] and not k["num"]),
        ("Both favour the pick", lambda k: k["astro"] and k["num"]))}
    rep = model.load_report()
    return _T().TemplateResponse(request, "tennis_top.html", {
        "rows": rows, "market": market, "markets": TOP_MARKETS, "day": day, "days": days, "tour": tour, "tours": TOUR,
        "min_p": min_p, "astro": astro, "num": num, "odds": odds, "agree": AGREE,
        "score_all": tally(pool), "score_day": tally(rows), "by_view": by_view, "verdicts": rep.get("verdicts"),
        "qs": urllib.parse.urlencode({k: v for k, v in {"day": day, "tour": tour, "min_p": min_p, "astro": astro, "num": num,
                                                         "odds": odds}.items() if v}),
        "page": "tennis_top"})


# ----------------------------------------------------------------------------- live record
LIVE_MARKETS = [("set", "Sets"), ("first", "First set"), ("match", "Match"), ("one_set", "At least one set"),
                ("dog_set", "Underdog wins a set")]


def _ll(p: float, y: int) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def compare_sources(rows: list[dict]) -> list[dict]:
    """On settled forecasts: the statistics model, the expected figure and the odds, set by set and match by match
    (log loss: lower is better), each on the matches it covers."""
    done = [r for r in rows if r["status"] == "settled" and r["pre_kickoff"]]
    out = []
    for name, get in (("Statistics model", lambda r: r["p"]), ("Expected (headline)", lambda r: r["e"]),
                      ("Odds alone", lambda r: (r["p"].get("market") or {}) if "a_set" in (r["p"].get("market") or {}) else None)):
        sets_ll, sets_hit, n_sets, m_ll, m_hit, n = 0.0, 0, 0, 0.0, 0, 0
        for r in done:
            q = get(r)
            if not q:
                continue
            n += 1
            for c in r["result"]["set_winners"]:
                y = int(c == "1")
                sets_ll += _ll(q["a_set"], y)
                sets_hit += int((q["a_set"] >= 0.5) == bool(y))
                n_sets += 1
            y = int(r["result"]["winner"] == 1)
            m_ll += _ll(q["a_match"], y)
            m_hit += int((q["a_match"] >= 0.5) == bool(y))
        out.append({"name": name, "n": n, "n_sets": n_sets,
                    "set_ll": sets_ll / n_sets if n_sets else None, "set_acc": sets_hit / n_sets if n_sets else None,
                    "match_ll": m_ll / n if n else None, "match_acc": m_hit / n if n else None})
    return out


def calibration(rows: list[dict]) -> list[dict]:
    """Set picks grouped by their probability: did the favoured player win sets as often as forecast?"""
    done = [r for r in rows if r["status"] == "settled" and r["pre_kickoff"]]
    edges = (0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.0001)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = [r for r in done if lo <= r["p_set_pick"] < hi]
        n = sum(r["sets_played"] for r in b)
        out.append({"band": f"{int(100 * lo)}–{min(100, int(100 * hi))}%", "matches": len(b), "n": n,
                    "hits": sum(r["set_hits"] for r in b), "rate": sum(r["set_hits"] for r in b) / n if n else None,
                    "expected": sum(r["p_set_pick"] * r["sets_played"] for r in b) / n if n else None})
    return out


@router.get("/tennis/live", response_class=HTMLResponse)
def tennis_live(request: Request, date_from: str = "", date_to: str = "", status: str = "", tour: str = "",
                surface: str = "", player: str = "", event: str = "", market: str = "set", hit: str = "", astro: str = "",
                num: str = "", odds: str = "", min_p: str = "", page_no: int = 1, msg: str = "", syncing: int = 0):
    from .app import SYNC
    market = market if market in dict(LIVE_MARKETS) else "set"
    recs = tlive.records()
    integrity = {"n": len(recs), "verified": sum(bool(r["verified"]) for r in recs),
                 "late": sum(not r["pre_kickoff"] for r in recs)}
    try:
        mp = float(min_p) if min_p else 0.0
    except ValueError:
        mp = 0.0
    t = player.lower().strip()
    rows = []
    for r in sorted(recs, key=lambda r: r["start_utc"], reverse=True):
        d = r["start_utc"][:10]
        if (date_from and d < date_from) or (date_to and d > date_to) or (status and r["status"] != status) \
                or (tour and r["tour"] != tour) or (surface and r["surface"] != surface) or (odds and not r.get("odds")) \
                or (t and t not in r["p1"].lower() and t not in r["p2"].lower()) \
                or (event and event.lower() not in r["event"].lower()):
            continue
        r["dayv"] = day_of(r)
        r["pick"] = pick_of(r, market)
        k = r["pick"]
        if k["p"] < mp or (astro and (astro == "yes") != k["astro"]) or (num and (num == "yes") != k["num"]):
            continue
        if hit:
            if k["hit"] is None:
                continue
            won = k["hit"] * 2 > k["n"] if market == "set" else bool(k["hit"])
            if (hit == "hit") != won:
                continue
        rows.append(r)
    done = [r for r in rows if r["pick"]["hit"] is not None and r["pre_kickoff"]]
    n = sum(r["pick"]["n"] for r in done)
    subset = {"n": n, "hits": sum(r["pick"]["hit"] for r in done), "matches": len(done),
              "expected": sum(r["pick"]["p"] * r["pick"]["n"] for r in done) / n if n else None}
    subset["rate"] = subset["hits"] / n if n else None
    per = 50
    pages = max(1, math.ceil(len(rows) / per))
    page_no = min(max(page_no, 1), pages)
    q = {"date_from": date_from, "date_to": date_to, "status": status, "tour": tour, "surface": surface, "player": player,
         "event": event, "market": market, "hit": hit, "astro": astro, "num": num, "odds": odds, "min_p": min_p}
    return _T().TemplateResponse(request, "tennis_live.html", {
        "rows": rows[(page_no - 1) * per: page_no * per], "n": len(rows), "page_no": page_no, "pages": pages, "q": q,
        "qs": urllib.parse.urlencode({k: v for k, v in q.items() if v}), "integrity": integrity,
        "tr": tlive.track_record(recs), "subset": subset, "compare": compare_sources(rows), "calib": calibration(rows),
        "markets": LIVE_MARKETS, "tours": TOUR, "agree": AGREE, "msg": msg, "syncing": bool(syncing) or SYNC["running"],
        "has_token": sync.token() is not None, "page": "tennis_live"})
