"""One list of games: the live track record plus the games added by hand (Analyze), without duplicates.

The live ledger (GitHub, sealed) stays the only *official* track record: its scores and integrity checks are
unchanged. Manual games are shown alongside, marked "manual", converted to the same shape so every page
(Live record, Top picks, Dataset) can list, filter and score them.

Duplicates. Two entries are the same game when their kickoffs are within 6 hours and both clubs' names
match (either way round, for neutral venues). The sealed live forecast wins; a manual entry for the same
game is folded into it (its page stays reachable from the live row). Analyze refuses to save a game that
already exists (find_duplicate).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import live, overunder, teamgoals
from .results2 import similarity

MANUAL_DIV = "MANUAL"
SAME_GAME_HOURS = 6
NAME_MATCH = 0.6


def _ko(s: str) -> datetime:
    return datetime.fromisoformat(s)


def same_game(home1: str, away1: str, ko1: str, home2: str, away2: str, ko2: str) -> bool:
    return live.same_game(home1, away1, ko1, home2, away2, ko2, NAME_MATCH)


def to_record(row: dict) -> dict | None:
    """A manual game (db row) in the live-record shape (before live.join)."""
    try:
        a = json.loads(row["analysis_json"])
    except (TypeError, ValueError):
        return None
    b_home = row.get("home_side") == "B"
    home, away = (row["team_b"], row["team_a"]) if b_home else (row["team_a"], row["team_b"])
    mk = a["market"]
    preds = {"market": {"fav": mk["p_fav"], "draw": mk["p_draw"], "dog": mk["p_dog"]},
             "synthesis": {k: a["synthesis"]["probabilities"][k] for k in ("fav", "draw", "dog")}}
    e4 = a.get("engine4")
    if e4:
        preds["engine4"] = {"fav": e4["p_fav"], "draw": e4["p_draw"], "dog": e4["p_dog"]}
    for k, v in a["verdicts"].items():
        preds[k] = {"winner": v["winner"], "goals_fav": v["goals_fav"], "goals_dog": v["goals_dog"],
                    "net": v.get("net"), "confidence": v.get("confidence")}
    oa, ob = row.get("odds_a"), row.get("odds_b")
    odds = {"home": ob if b_home else oa, "draw": row.get("odds_d"), "away": oa if b_home else ob}
    ko = row["kickoff_utc"]
    committed = row.get("created_at") or ko
    return {"match_key": f"m-{row['id']}", "manual_id": row["id"], "division": MANUAL_DIV,
            "league": "Added manually", "home": home, "away": away, "kickoff_utc": ko,
            "odds": odds, "odds_source": row.get("odds_source") or "entered by hand",
            "p_over25": a.get("inputs", {}).get("p_over25"),
            "venue_lat": row.get("lat"), "venue_lon": row.get("lon"), "venue_source": row.get("loc_source"),
            "favourite": a["fav"], "underdog": a["dog"], "fav_is_home": a["fav"] == home,
            # a historical entry added after the match is never a pre-kickoff forecast
            "committed_at": ko if row.get("post_hoc") else committed,
            "model_version": e4["version"] if e4 else None, "predictions": preds, "sha256": None}


def manual_result(row: dict) -> dict | None:
    if row.get("status") in ("abandoned", "walkover"):
        return {"void": True, "reason": row["status"]}
    if row.get("score_a") is None or row.get("score_b") is None:
        return None
    b_home = row.get("home_side") == "B"
    sa, sb = int(row["score_a"]), int(row["score_b"])
    return {"goals_home": sb if b_home else sa, "goals_away": sa if b_home else sb, "source": "entered by hand"}


def manual_records(rows: list[dict]) -> list[dict]:
    ou_cal, ts_cal = overunder.load(), teamgoals.load()
    out = []
    for row in rows:
        rec = to_record(row)
        if rec is None:
            continue
        j = live.join(rec, manual_result(row), ou_cal, ts_cal)
        j.update(origin="manual", url=f"/match/{row['id']}", verified=True)
        out.append(j)
    return out


def all_records(rows: list[dict], live_recs: list[dict] | None = None, include_withdrawn: bool = False) -> list[dict]:
    """Live records plus manual games, newest kickoff first, each game once. Forecasts withdrawn before
    kickoff (duplicates, name mix-ups) are left out unless include_withdrawn, and never absorb a manual game."""
    live_recs = live.records() if live_recs is None else live_recs
    withdrawn = [r for r in live_recs if r.get("withdrawn")]
    kept = [r for r in live_recs if not r.get("withdrawn")]
    for m in sorted(manual_records(rows), key=lambda r: r["committed_at"]):
        twin = next((r for r in kept if same_game(m["home"], m["away"], m["kickoff_utc"],
                                                   r["home"], r["away"], r["kickoff_utc"])), None)
        if twin is None:
            kept.append(m)
        else:
            twin.setdefault("also", []).append(m["url"])
    if include_withdrawn:
        kept += withdrawn
    kept.sort(key=lambda r: r["kickoff_utc"], reverse=True)
    return kept


def find_duplicate(team_a: str, team_b: str, kickoff_utc: str, rows: list[dict],
                   preds: list[dict] | None = None) -> tuple[str, str] | None:
    """An existing game this new entry would duplicate: ("manual", match id) or ("live", match key)."""
    preds = live.read_predictions() if preds is None else preds
    voided = {k for k, v in live.read_results().items() if v.get("void")} if preds else set()
    for p in preds:
        if p["match_key"] not in voided and same_game(team_a, team_b, kickoff_utc, p["home"], p["away"], p["kickoff_utc"]):
            return "live", p["match_key"]
    for r in rows:
        if same_game(team_a, team_b, kickoff_utc, r["team_a"], r["team_b"], r["kickoff_utc"]):
            return "manual", r["id"]
    return None
