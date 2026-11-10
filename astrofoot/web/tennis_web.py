"""Tennis section of the web app: forecasts (live record), match breakdown, analyze, model (ML) and dataset."""
from __future__ import annotations

import math
import re
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import db, sync
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
        names = {i: n for i, n in names.items() if not features.placeholder(i, n)}
        tours = {}
        if len(m):
            for i, t in zip(pd.concat([m.p1_id, m.p2_id]), pd.concat([m.tour, m.tour])):
                tours[str(i)] = t
        _STATE.update(key=key, matches=m, players=pl, pdict=features.players_dict(pl), st=st, names=names, tours=tours)
    return _STATE


def records() -> list[dict]:
    """Tennis forecasts with any odds you entered by hand applied (see tennis.live.with_odds), plus the matches you
    added yourself on Analyze ('manual': not sealed, never in the official track record)."""
    from ..tennis.odds import same_player
    from .app import con
    try:
        c = con()
        uo, manual = db.tennis_odds(c), db.tennis_manual(c)
    except Exception:  # noqa: BLE001
        uo, manual = {}, []
    recs = tlive.records(user_odds=uo) if uo else tlive.records()
    for rec, res in manual:
        # once ESPN lists the same match, the sealed forecast takes over
        t = pd.Timestamp(rec["start_utc"])
        if any(abs((pd.Timestamp(r["start_utc"]) - t).total_seconds()) < 36 * 3600
               and ((same_player(rec["p1"], r["p1"]) and same_player(rec["p2"], r["p2"]))
                    or (same_player(rec["p1"], r["p2"]) and same_player(rec["p2"], r["p1"]))) for r in recs):
            continue
        o = uo.get(rec["match_id"])
        j = tlive.join(tlive.with_odds({**rec, "odds": None}, o) if o else rec, res)
        j.update(verified=None, manual=True)
        recs.append(j)
    return sorted(recs, key=lambda r: r["start_utc"])


def parse_score(text: str, best_of: int = 3, winner: int | None = None) -> dict | None:
    """'6-4 3-6 7-6' (player 1's games first) → set winners and the match winner. Only completed sets count (6+
    games, or a deciding tie-break to 10). A retirement ('ret') needs the winner given; None if not readable."""
    sets = [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*[-–:]\s*(\d+)", text or "")]
    done = [(a, b) for a, b in sets if a != b and max(a, b) >= 6 or max(a, b) >= 10]
    sw = "".join("1" if a > b else "2" for a, b in done)
    retired = bool(re.search(r"ret|w/?o|walkover", text or "", re.I))
    w1, w2 = sw.count("1"), sw.count("2")
    need = 3 if best_of == 5 else 2
    if not retired:
        if max(w1, w2) < need:
            return None
        winner = 1 if w1 > w2 else 2
    elif winner not in (1, 2):
        return None
    if not sw:
        return {"winner": None, "set_winners": "", "score": text.strip(), "retired": retired, "void": True,
                "void_reason": "no set completed"}
    return {"winner": winner, "set_winners": sw, "score": " ".join(f"{a}-{b}" for a, b in sets) + (" ret." if retired else ""),
            "retired": retired, "void": False}


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
        ("Last 5 matches won (share)", num("a_form5"), num("b_form5"), "see the last five below"),
        ("Sets won share, last 5 matches (A − B)", num("sets5_diff"), None, ""),
        ("Last 5 meetings: wins A − B", num("h2h5_diff", 0), None, "+1 = A won the last meeting" if f.get("h2h_last") == 1
         else ("+1 = B won the last meeting" if f.get("h2h_last") == -1 else "no meeting yet")),
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
    if rec.get("day") and "tz" in rec["day"]:      # sealed with the venue's day: as sealed
        return rec["day"]
    # sealed before the day was taken at the venue (or without a reading): worked out now from the dates and venue
    m = {"p1_id": rec["p1_id"], "p2_id": rec["p2_id"], "p1": rec["p1"], "p2": rec["p2"], "date": rec["start_utc"],
         "venue": rec.get("venue") or ""}
    return tlive.day_compare(m, state()["pdict"])


def edge_pts(logit: float | None) -> float | None:
    """A learned log-odds edge as percentage points on an even set (50% → 50% + this)."""
    if logit is None:
        return None
    return 100 * (1 / (1 + math.exp(-logit)) - 0.5)


def _view_score(score: str, flip: bool) -> str:
    return " ".join("-".join(reversed(x.split("-"))) for x in str(score).split()) if flip else str(score)


def recent(pid: str, before, n: int = 5, opp: str | None = None) -> list[dict]:
    """A player's last n completed matches before a moment (or the last n meetings with `opp`), newest first,
    from the ESPN history: date, tournament, round, surface, opponent, won/lost and the score from their side."""
    m = state()["matches"]
    if not len(m) or not pid:
        return []
    when = pd.Timestamp(before)
    when = when.tz_localize("UTC") if when.tzinfo is None else when
    mine = (m.p1_id == pid) | (m.p2_id == pid)
    if opp:
        mine &= (m.p1_id == opp) | (m.p2_id == opp)
    sub = m[mine & m.completed & ~m.walkover & (m.date < when) & (m.set_winners.fillna("").str.len() > 0)]
    out = []
    for r in sub.sort_values("date").tail(n).iloc[::-1].to_dict("records"):
        first = r["p1_id"] == pid
        out.append({"date": r["date"].strftime("%Y-%m-%d"), "event": r["event"], "round": r["round"], "surface": r["surface"],
                    "opponent": r["p2"] if first else r["p1"], "won": (r["winner"] == 1) == first,
                    "score": _view_score(r["score"], not first), "retired": bool(r.get("retired"))})
    return out


def last_five(p1_id: str, p2_id: str, before) -> dict:
    return {"a": recent(p1_id, before), "b": recent(p2_id, before), "h2h": recent(p1_id, before, 5, opp=p2_id)}


def _bundle_groups():
    b = model.load()
    return (b or {}).get("groups") or [], (b or {}).get("version")


# ----------------------------------------------------------------------------- pages
DAY_FAVOURS = [("", "any"), ("both", "astrology and numerology favour the same player"),
               ("split", "they favour different players"), ("astro", "astrology favours a player"),
               ("num", "numerology favours a player")]


def day_favours_ok(dv: dict, want: str) -> bool:
    a, n = dv["astro"]["favours"], dv["num"]["favours"]
    return {"both": a > 0 and a == n, "split": a > 0 and n > 0 and a != n, "astro": a > 0, "num": n > 0}.get(want, True)


@router.get("/tennis", response_class=HTMLResponse)
def tennis_home(request: Request, day: str = "", tour: str = "", status: str = "", favours: str = ""):
    from .app import _day_label  # noqa: F401
    recs = records()
    tr_all = tlive.track_record(recs)
    days = sorted({r["start_utc"][:10] for r in recs}, reverse=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if day not in days and day != "all":
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else "all")
    rows = [r for r in recs if (day == "all" or r["start_utc"][:10] == day) and (not tour or r["tour"] == tour)
            and (not status or r["status"] == status)]
    for r in rows:
        r["dayv"] = day_of(r)
    favours = favours if favours in dict(DAY_FAVOURS) else ""
    shown_all = len(rows)
    rows = [r for r in rows if day_favours_ok(r["dayv"], favours)]
    rep = model.load_report()
    return _T().TemplateResponse(request, "tennis_home.html", {
        "favours": favours, "favour_choices": DAY_FAVOURS, "hidden": shown_all - len(rows),
        "rows": rows, "day": day, "days": days, "tour": tour, "status": status, "tours": TOUR, "tr": tr_all,
        "tr_day": tlive.track_record(rows), "n": len(recs), "rep": rep, "has_model": model.BUNDLE.exists(),
        "has_data": (DATA / "matches.parquet").exists(), "page": "tennis_home"})


ANALYZE_FIELDS = ("a", "b", "when", "surface", "best_of", "tour", "round", "event", "a_seed", "b_seed", "a_dob", "b_dob",
                  "venue", "a_odds", "b_odds")


def json_safe(o):
    import json
    return json.loads(json.dumps(o, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else
                                 (x.item() if hasattr(x, "item") else str(x))).replace("NaN", "null"))


@router.post("/tennis/analyze/save")
async def tennis_analyze_save(request: Request):
    """Add the analysed match to your tennis matches (shown everywhere with a 'manual' badge)."""
    from .app import con
    form = await request.form()
    kw = {k: str(form.get(k, "")) for k in ANALYZE_FIELDS}
    kw["best_of"] = 5 if kw["best_of"] == "5" else 3
    kw["surface"] = kw["surface"] or "hard"
    kw["round"] = kw["round"] or "Round 1"
    resp = tennis_analyze(request, **kw)
    out = resp.context.get("out")
    if not out or not out.get("p"):
        raise HTTPException(400, "nothing to save: analyse a match first (and a trained model is needed)")
    m, p = out["m"], out["p"]
    odds = None
    if kw["a_odds"] and kw["b_odds"]:
        try:
            odds = {"a": float(kw["a_odds"]), "b": float(kw["b_odds"]), "source": "entered by you", "manual": True,
                    "entered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "after_start": False}
        except ValueError:
            odds = None
    f = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in out["f"].items()
         if not k.startswith(("d_astro_", "d_num_")) or k in ("d_astro_rule", "d_num_rule")}
    rec = {"manual": True, "tour": m["tour"], "event": m["event"] or "Added by you", "round": m["round"], "venue": m["venue"],
           "surface": m["surface"], "best_of": m["best_of"], "start_utc": m["date"].isoformat(), "p1": m["p1"], "p1_id": m["p1_id"],
           "p1_seed": m["p1_seed"], "p1_country": m.get("p1_country"), "p2": m["p2"], "p2_id": m["p2_id"], "p2_seed": m["p2_seed"],
           "p2_country": m.get("p2_country"), "model_version": p["version"], "p": p, "features": f, "day": out["day"],
           "odds": odds, "committed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": ""}
    mid = db.add_tennis_manual(con(), json_safe(rec))
    return RedirectResponse(f"/tennis/match/{mid}?msg=" + urllib.parse.quote("Added to your tennis matches."), status_code=303)


@router.post("/tennis/match/{mid}/result")
async def tennis_manual_result(request: Request, mid: str):
    """Result (or removal) of a match you added yourself."""
    from .app import con
    form = await request.form()
    c = con()
    if not mid.startswith("u"):
        raise HTTPException(400, "only matches you added can be edited")
    if form.get("delete"):
        db.delete_tennis_manual(c, mid)
        return RedirectResponse("/tennis?day=all", status_code=303)
    rec = next((r for r, _ in db.tennis_manual(c) if r["match_id"] == mid), None)
    if rec is None:
        raise HTTPException(404)
    if form.get("void"):
        db.set_tennis_manual_result(c, mid, {"winner": None, "set_winners": "", "score": "", "retired": False, "void": True,
                                             "void_reason": "marked void by you"})
        msg = "Marked void."
    elif form.get("clear"):
        db.set_tennis_manual_result(c, mid, None)
        msg = "Result cleared."
    else:
        w = str(form.get("winner", ""))
        res = parse_score(str(form.get("score", "")), int(rec.get("best_of") or 3), int(w) if w in ("1", "2") else None)
        if res is None:
            msg = ("Could not read a finished score: type the sets with the first-listed player's games first, e.g. "
                   "6-4 3-6 7-6. For a retirement add 'ret' and choose the winner.")
        else:
            db.set_tennis_manual_result(c, mid, res)
            msg = "Result saved."
    return RedirectResponse(f"/tennis/match/{mid}?msg=" + urllib.parse.quote(msg), status_code=303)


@router.post("/tennis/match/{mid}/odds")
async def tennis_match_odds(request: Request, mid: str):
    """Save (or with remove=1, delete) odds typed in by hand for a forecast sealed without odds."""
    from .app import con
    form = await request.form()
    back = str(form.get("back") or "")
    back = back if back.startswith("/tennis") else f"/tennis/match/{mid}"
    if form.get("remove"):
        db.delete_tennis_odds(con(), mid)
        msg = "Odds removed."
    else:
        try:
            a, b = float(str(form.get("a", "")).replace(",", ".")), float(str(form.get("b", "")).replace(",", "."))
            if a <= 1.0 or b <= 1.0:
                raise ValueError
            db.set_tennis_odds(con(), mid, a, b)
            msg = "Odds saved: every page now uses them for this match."
        except ValueError:
            msg = "Odds must be decimal numbers above 1.00, e.g. 1.45 and 2.80."
    sep = "&" if "?" in back else "?"
    return RedirectResponse(f"{back}{sep}msg={urllib.parse.quote(msg)}", status_code=303)


@router.get("/tennis/match/{mid}", response_class=HTMLResponse)
def tennis_match(request: Request, mid: str, msg: str = ""):
    rec = next((r for r in records() if r["match_id"] == mid), None)
    if rec is None:
        raise HTTPException(404)
    groups, _ = _bundle_groups()
    return _T().TemplateResponse(request, "tennis_match.html", {
        "r": rec, "p": rec["p"], "x": explain(rec["features"], rec), "used": groups, "sealed": True, "day": day_of(rec),
        "msg": msg, "five": last_five(rec["p1_id"], rec["p2_id"], rec["start_utc"]),
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
               "day": tlive.day_compare(m, pdict), "five": last_five(ids["a"], ids["b"], m["date"]),
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


DATASET_ROUNDS = [("qualifying", "Qualifying"), ("early", "Round 1 to 3"), ("r16", "Round of 16"), ("qf", "Quarterfinal"),
                  ("sf", "Semifinal"), ("final", "Final")]
SEEDS = [("", "any"), ("both", "both seeded"), ("one", "one seeded"), ("none", "neither seeded"), ("upset", "unseeded beat a seed")]
DAY_FILTER = [("", "any"), ("won", "favoured player won"), ("lost", "favoured player lost"), ("level", "level (no favourite)")]


def _round_key(name: str) -> str:
    n = (name or "").lower()
    if "qualif" in n:
        return "qualifying"
    for k, words in (("final", ("final",)), ("sf", ("semi",)), ("qf", ("quarter",)), ("r16", ("round of 16", "4th round", "fourth"))):
        if any(w in n for w in words) and not (k == "final" and ("semi" in n or "quarter" in n)):
            return k
    return "early"


def day_verdicts(m: pd.DataFrame) -> pd.DataFrame:
    """Who the date-only astrology and numerology favoured in each match (0 level, 1 or 2), cached per data version."""
    from functools import lru_cache

    from ..tennis import daychart
    s = state()
    cache = s.setdefault("verdicts", {})
    pd_ = s["pdict"]

    @lru_cache(maxsize=None)
    def astro(pid, day, tz):
        return daychart.astro_day((pd_.get(pid) or {}).get("dob"), day, tz)["score"]

    @lru_cache(maxsize=None)
    def num(pid, name, day):
        p = pd_.get(pid) or {}
        return daychart.num_day(p.get("dob"), p.get("full_name") or name, day)["score"]

    todo = [i for i in m["id"] if i not in cache]
    if todo:
        sub = m[m["id"].isin(set(todo))]
        from ..tennis.venue import local_day
        for mid, a, b, na, nb, when, ven in zip(sub["id"], sub.p1_id, sub.p2_id, sub.p1, sub.p2, sub.date, sub.venue.fillna("")):
            d, tz = local_day(ven, when)             # the match day at the venue
            cache[mid] = (daychart.verdict(astro(a, d, tz), astro(b, d, tz)), daychart.verdict(num(a, na, d), num(b, nb, d), 0.4))
    v = [cache[i] for i in m["id"]]
    return pd.DataFrame({"astro_fav": [x[0] for x in v], "num_fav": [x[1] for x in v]}, index=m.index)


def _day_ok(fav: pd.Series, winner: pd.Series, want: str) -> pd.Series:
    if want == "won":
        return (fav > 0) & (fav == winner)
    if want == "lost":
        return (fav > 0) & (fav != winner)
    if want == "level":
        return fav == 0
    return pd.Series(True, index=fav.index)


@router.get("/tennis/dataset", response_class=HTMLResponse)
def tennis_dataset(request: Request, tour: str = "", surface: str = "", year: str = "", player: str = "", event: str = "",
                   date_from: str = "", date_to: str = "", round: str = "", seeds: str = "", best_of: str = "",
                   astro: str = "", num: str = "", check: str = "", page_no: int = 1):
    s = state()
    m = s["matches"]
    years, stats = [], None
    if len(m):
        m = m[m.completed & ~m.walkover & (m.set_winners.fillna("").str.len() > 0)]
        years = sorted({int(y) for y in m.date.dt.year.unique()}, reverse=True)
        if tour:
            m = m[m.tour == tour]
        if surface:
            m = m[m.surface == surface]
        if year.isdigit():
            m = m[m.date.dt.year == int(year)]
        day = m.date.dt.strftime("%Y-%m-%d")
        if date_from:
            m = m[day >= date_from]
        if date_to:
            m = m[day.reindex(m.index) <= date_to]
        if player:
            t = player.lower()
            m = m[m.p1.str.lower().str.contains(t, regex=False) | m.p2.str.lower().str.contains(t, regex=False)]
        if event:
            m = m[m.event.str.lower().str.contains(event.lower(), regex=False)]
        if round in dict(DATASET_ROUNDS):
            m = m[m["round"].map(_round_key) == round]
        if best_of in ("3", "5"):
            m = m[m.best_of.astype(int) == int(best_of)]
        if seeds:
            s1, s2 = m.p1_seed.notna() & (m.p1_seed > 0), m.p2_seed.notna() & (m.p2_seed > 0)
            if seeds == "both":
                m = m[s1 & s2]
            elif seeds == "one":
                m = m[s1 ^ s2]
            elif seeds == "none":
                m = m[~s1 & ~s2]
            elif seeds == "upset":
                m = m[(s1 & ~s2 & (m.winner == 2)) | (s2 & ~s1 & (m.winner == 1))]
        if astro or num or check:
            m = m.join(day_verdicts(m))
            # how often the day's favourite won, under every filter except the day ones (else it is circular)
            stats = {}
            for k, label in (("astro_fav", "Astrology"), ("num_fav", "Numerology")):
                f = m[m[k] > 0]
                stats[label] = {"n": len(f), "won": int((f[k] == f.winner).sum())}
            both = m[(m.astro_fav > 0) & (m.astro_fav == m.num_fav)]
            stats["Astrology and numerology together"] = {"n": len(both), "won": int((both.astro_fav == both.winner).sum())}
            m = m[_day_ok(m.astro_fav, m.winner, astro) & _day_ok(m.num_fav, m.winner, num)]
        m = m.sort_values("date", ascending=False)
    per = 50
    pages = max(1, math.ceil(len(m) / per))
    page_no = min(max(page_no, 1), pages)
    page = m.iloc[(page_no - 1) * per: page_no * per] if len(m) else m
    if len(page):
        page = page.drop(columns=[c for c in ("astro_fav", "num_fav") if c in page]).join(day_verdicts(page))
    rows = page.to_dict("records") if len(page) else []
    for r in rows:      # score from the winner's side
        if r.get("winner") == 2:
            r["score"] = " ".join("-".join(reversed(x.split("-"))) for x in str(r["score"]).split())
    q = {"tour": tour, "surface": surface, "year": year, "player": player, "event": event, "date_from": date_from,
         "date_to": date_to, "round": round, "seeds": seeds, "best_of": best_of, "astro": astro, "num": num, "check": check}
    by_surface = m.surface.value_counts().to_dict() if len(m) else {}
    from .app import SECTIONS
    return _T().TemplateResponse(request, "tennis_dataset.html", {
        "rows": rows, "n": len(m), "page_no": page_no, "pages": pages, "years": years, "q": q, "tours": TOUR,
        "qs": urllib.parse.urlencode({k: v for k, v in q.items() if v}), "by_surface": by_surface, "stats": stats,
        "rounds": DATASET_ROUNDS, "seed_choices": SEEDS, "day_filter": DAY_FILTER,
        "sections": {**SECTIONS, "tennis": "Tennis"},
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
    recs = [r for r in records() if r["status"] != "void"]
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
                num: str = "", odds: str = "", min_p: str = "", page_no: int = 1, msg: str = "", syncing: int = 0,
                favours: str = ""):
    from .app import SYNC
    market = market if market in dict(LIVE_MARKETS) else "set"
    recs = records()
    sealed = [r for r in recs if not r.get("manual")]
    integrity = {"n": len(sealed), "verified": sum(bool(r["verified"]) for r in sealed),
                 "late": sum(not r["pre_kickoff"] for r in sealed), "manual": len(recs) - len(sealed)}
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
        if k["p"] < mp or (astro and (astro == "yes") != k["astro"]) or (num and (num == "yes") != k["num"]) \
                or not day_favours_ok(r["dayv"], favours):
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
         "event": event, "market": market, "hit": hit, "astro": astro, "num": num, "odds": odds, "min_p": min_p,
         "favours": favours}
    return _T().TemplateResponse(request, "tennis_live.html", {
        "favour_choices": DAY_FAVOURS,
        "rows": rows[(page_no - 1) * per: page_no * per], "n": len(rows), "page_no": page_no, "pages": pages, "q": q,
        "qs": urllib.parse.urlencode({k: v for k, v in q.items() if v}), "integrity": integrity,
        "tr": tlive.track_record(recs), "subset": subset, "compare": compare_sources(rows), "calib": calibration(rows),
        "markets": LIVE_MARKETS, "tours": TOUR, "agree": AGREE, "msg": msg, "syncing": bool(syncing) or SYNC["running"],
        "has_token": sync.token() is not None, "page": "tennis_live"})
