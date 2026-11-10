"""Tennis → My picks: slips of tennis picks (match, first set, at least one set), kept apart from soccer."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from .. import db
from .. import mypicks as fmp
from ..tennis import live as tlive
from ..tennis import mypicks as tmp
from .tennis_web import day_of

router = APIRouter()
SECTION = "tennis"


def _con():
    from .app import con
    return con()


def _T():
    from .app import T
    return T


def _games() -> dict[str, dict]:
    out = {}
    for r in tlive.records():
        r["dayv"] = day_of(r)
        out[r["match_id"]] = r
    return out


def _view(saved: list[dict], games: dict, now_iso: str) -> list[dict]:
    out = []
    for p in saved:
        g = games.get(p["match_key"])
        res = g.get("result") if g else None
        hit = None
        if res and not res.get("void"):
            hit = tmp.won(p["selection"], res["set_winners"], res["winner"])
        out.append({**p, "late": p["picked_at"] >= p["kickoff_utc"], "result": res, "hit": hit,
                    "status": g["status"] if g else "unknown", "started": p["kickoff_utc"] <= now_iso,
                    "opts": tmp.options(g) if g else [], "fav": tmp.favours(p["selection"], g["dayv"]) if g else None,
                    "game": g})
    return out


def _summary(picks: list[dict]) -> dict:
    from .app import _slip_summary
    return _slip_summary(picks)


def _pick_from(g: dict, code: str, now_iso: str) -> dict | None:
    opts = tmp.options(g)
    o = next((x for x in opts if x["code"] == code), opts[0] if opts and not code else None)
    if o is None:
        return None
    return {"match_key": g["match_id"], "kickoff_utc": g["start_utc"], "home": g["p1"], "away": g["p2"],
            "league": f"{g['tour'].upper()} · {g['event']}", "selection": o["code"], "label": o["label"], "p": o["p"],
            "url": f"/tennis/match/{g['match_id']}", "picked_at": now_iso}


def _slip(c, sid) -> dict:
    x = db.get_slip(c, sid)
    if x is None or x.get("section") != SECTION:
        raise HTTPException(404, "slip not found")
    return x


FILTERS = [("", "any"), ("astro", "astrology favours the most likely pick"), ("num", "numerology favours it"),
           ("both", "both favour it")]


@router.get("/tennis/mypicks", response_class=HTMLResponse)
def tennis_mypicks(request: Request, day: str = "", slip: int = 0, added: int = -1, changed: int = -1, removed: int = -1,
                   dup: int = 0, tour: str = "", fav: str = "", odds: str = ""):
    c = _con()
    games = _games()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    days = sorted({g["start_utc"][:10] for g in games.values()}, reverse=True)
    today = now_iso[:10]
    if not day:
        day = today if today in days else next((d for d in sorted(days) if d >= today), days[0] if days else today)
    day_slips = db.slips(c, day, SECTION)
    if not day_slips:
        db.create_slip(c, day, section=SECTION)
        day_slips = db.slips(c, day, SECTION)
    active = next((x for x in day_slips if x["id"] == slip), day_slips[-1] if not slip else day_slips[0])
    day_view = _view(db.my_picks(c, day, section=SECTION), games, now_iso)
    for x in day_slips:
        x.update(_summary([p for p in day_view if p["slip_id"] == x["id"]]))
    slip_picks = [p for p in day_view if p["slip_id"] == active["id"]]
    in_slip = {p["match_key"]: p for p in slip_picks}
    in_any: dict[str, list[str]] = {}
    for p in day_view:
        in_any.setdefault(p["match_key"], []).append(p["slip_name"])
    rows, hidden = [], 0
    for g in sorted((g for g in games.values() if g["start_utc"][:10] == day and g["status"] != "void"),
                    key=lambda g: (g["start_utc"], g["p1"])):
        opts = tmp.options(g)
        f = tmp.favours(opts[0]["code"], g["dayv"])
        if (tour and g["tour"] != tour) or (odds and not g.get("odds")) or (fav == "astro" and not f["astro"]) \
                or (fav == "num" and not f["num"]) or (fav == "both" and f["count"] < 2):
            hidden += 1
            continue
        pick = in_slip.get(g["match_id"])
        rows.append({"g": g, "opts": opts, "pick": pick, "chosen": pick["selection"] if pick else opts[0]["code"],
                     "started": g["start_utc"] <= now_iso, "fav": f,
                     "elsewhere": [n for n in in_any.get(g["match_id"], []) if n != active["name"]]})
    all_view = _view(db.my_picks(c, section=SECTION), games, now_iso)
    keep = "".join(f"&{k}={v}" for k, v in (("tour", tour), ("fav", fav), ("odds", odds)) if v)
    return _T().TemplateResponse(request, "tennis_mypicks.html", {
        "day": day, "days": days, "rows": rows, "hidden": hidden, "slips": day_slips, "active": active,
        "day_picks": slip_picks, "slip_sum": _summary(slip_picks), "added": added, "changed": changed, "removed": removed,
        "dup": dup, "score_day": fmp.score(day_view), "score_all": fmp.score(all_view), "n_all": len(all_view),
        "n_day": len(day_view), "tour": tour, "fav": fav, "odds": odds, "filters": FILTERS, "keep": keep,
        "page": "tennis_mypicks"})


def _keep(form) -> str:
    return "".join(f"&{k}={form.get(k)}" for k in ("tour", "fav", "odds") if form.get(k))


@router.post("/tennis/mypicks/slip/new")
async def t_slip_new(request: Request):
    form = await request.form()
    day = str(form.get("day", ""))
    sid = db.create_slip(_con(), day, str(form.get("name", "")), section=SECTION)
    return RedirectResponse(f"/tennis/mypicks?day={day}&slip={sid}{_keep(form)}", status_code=303)


@router.post("/tennis/mypicks/slip/rename")
async def t_slip_rename(request: Request):
    form = await request.form()
    c = _con()
    x = _slip(c, form.get("slip"))
    db.rename_slip(c, x["id"], str(form.get("name", "")))
    return RedirectResponse(f"/tennis/mypicks?day={x['day']}&slip={x['id']}{_keep(form)}", status_code=303)


@router.post("/tennis/mypicks/slip/delete")
async def t_slip_delete(request: Request):
    form = await request.form()
    c = _con()
    x = _slip(c, form.get("slip"))
    db.delete_slip(c, x["id"])
    return RedirectResponse(f"/tennis/mypicks?day={x['day']}{_keep(form)}", status_code=303)


@router.post("/tennis/mypicks/add")
async def t_add(request: Request):
    form = await request.form()
    c = _con()
    x = _slip(c, form.get("slip"))
    games = _games()
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
    return RedirectResponse(f"/tennis/mypicks?day={x['day']}&slip={x['id']}&added={n}&dup={dup}{_keep(form)}#mine",
                            status_code=303)


@router.post("/tennis/mypicks/edit")
async def t_edit(request: Request):
    form = await request.form()
    c = _con()
    x = _slip(c, form.get("slip"))
    games = _games()
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
    return RedirectResponse(f"/tennis/mypicks?day={x['day']}&slip={x['id']}&changed={changed}&removed={removed}"
                            f"{_keep(form)}#mine", status_code=303)


def _report(date_from: str, date_to: str) -> dict:
    c = _con()
    games = _games()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    picks = [p for p in db.my_picks(c, section=SECTION)
             if (not date_from or p["day"] >= date_from) and (not date_to or p["day"] <= date_to)]
    rows = sorted(_view(picks, games, now_iso), key=lambda r: (r["day"], r["slip_id"], r["kickoff_utc"], r["home"]))
    slips = []
    for x in db.slips(c, section=SECTION):
        mine = [r for r in rows if r["slip_id"] == x["id"]]
        if mine:
            slips.append({**x, **_summary(mine), "rows": mine})
    by_fav = {}
    for r in rows:
        if r["fav"] is not None:
            by_fav.setdefault(r["fav"]["count"], []).append(r)
    pending = [r for r in rows if r["result"] is None and r["status"] != "void"]
    return {"rows": rows, "slips": slips, "generated": now_iso, "date_from": date_from, "date_to": date_to,
            "summary": {"n": len(rows), "scored": fmp.score(rows), "late": sum(r["late"] for r in rows),
                        "pending": len(pending), "all_pending_win": fmp.all_win(pending)},
            "by_fav": {k: fmp.score(v) for k, v in sorted(by_fav.items())}}


@router.get("/tennis/mypicks/report", response_class=HTMLResponse)
def t_report(request: Request, date_from: str = "", date_to: str = "", day: str = ""):
    if day and not (date_from or date_to):
        date_from = date_to = day
    return _T().TemplateResponse(request, "tennis_mypicks_report.html", {"r": _report(date_from, date_to),
                                                                          "page": "tennis_mypicks"})


@router.get("/tennis/mypicks/export.csv")
def t_csv(date_from: str = "", date_to: str = "", day: str = ""):
    if day and not (date_from or date_to):
        date_from = date_to = day
    rep = _report(date_from, date_to)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["day", "slip", "start_utc", "tour", "tournament", "round", "surface", "player_1", "player_2", "pick_market",
                "pick", "pick_probability", "astrology_favours_pick", "numerology_favours_pick", "odds_1", "odds_2",
                "p1_set", "p1_first", "p1_one_set", "p1_match", "p2_set", "p2_first", "p2_one_set", "p2_match",
                "astro_score_1", "astro_score_2", "num_score_1", "num_score_2", "seal_sha256", "picked_at",
                "picked_after_start", "status", "score", "pick_won"])
    for r in rep["rows"]:
        g = r["game"] or {}
        e = g.get("e") or {}
        d = (g.get("dayv") or {})
        o = g.get("odds") or {}
        res = r["result"] or {}
        f = r["fav"] or {}
        w.writerow([r["day"], r["slip_name"], r["kickoff_utc"], g.get("tour", ""), g.get("event", ""), g.get("round", ""),
                    g.get("surface", ""), r["home"], r["away"], tmp.MARKETS.get(r["selection"][0], ""), r["label"],
                    round(r["p"], 4) if r["p"] is not None else "", "yes" if f.get("astro") else "no",
                    "yes" if f.get("num") else "no", o.get("a", ""), o.get("b", ""),
                    *[round(e[k], 4) if k in e else "" for k in ("a_set", "a_first", "a_one_set", "a_match",
                                                                   "b_set", "b_first", "b_one_set", "b_match")],
                    *[((d.get(k) or {}).get(s) or {}).get("score", "") for k in ("astro", "num") for s in ("a", "b")],
                    g.get("sha256", ""), r["picked_at"], "yes" if r["late"] else "no", r["status"], res.get("score", ""),
                    "" if r["hit"] is None else ("yes" if r["hit"] else "no")])
    name = f"tennis-picks-{date_from or 'start'}-to-{date_to or 'latest'}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
