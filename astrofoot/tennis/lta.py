"""Challenger and team-event matches (Hopman Cup, United Cup, Davis / Billie Jean King Cup, Laver Cup) from the
Live Tennis API (livetennisapi.com), FREE tier: 100 requests a day, upcoming and live listings, and single-match
lookups (which also work after a match is finished). ESPN, the main source, has none of these.

The key is LIVETENNISAPI_KEY (a GitHub secret, like the soccer keys). Requests are counted per UTC day in
ledger/tennis/lta_state.json; listings come first, then result look-ups, always keeping RESERVE requests unused."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

API = "https://api.livetennisapi.com/api/public/v1"
SOURCE = "livetennisapi.com"
DAILY = 100
RESERVE = 10
PREFIX = "lta:"
TEAM_EVENTS = ("hopman", "united cup", "davis cup", "billie jean king", "fed cup", "laver cup")


def token() -> str | None:
    return os.environ.get("LIVETENNISAPI_KEY") or None


class Client:
    def __init__(self, key: str, state_path: Path, now: datetime, base: str = API):
        self.key, self.base, self.path = key, base, state_path
        self.state = json.loads(state_path.read_text()) if state_path.exists() else {}
        self.day = now.strftime("%Y-%m-%d")
        if self.state.get("day") != self.day:
            self.state = {"day": self.day, "used": 0}

    @property
    def left(self) -> int:
        return DAILY - RESERVE - int(self.state.get("used", 0))

    def get(self, path: str, **params):
        if self.left <= 0:
            raise RuntimeError("daily request budget used up")
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        req = urllib.request.Request(f"{self.base}{path}" + (f"?{q}" if q else ""),
                                     headers={"Authorization": f"Bearer {self.key}", "Accept": "application/json",
                                              "User-Agent": "astro-football-research"})
        self.state["used"] = int(self.state.get("used", 0)) + 1
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=1) + "\n")


def _venue(tournament: str) -> str:
    """The city in a tournament name ("Lima 2" → "Lima", "Sopo (Colombia)" → "Sopo, Colombia"), for the timezone."""
    m = re.match(r"\s*(.+?)\s*\(([^)]+)\)", tournament or "")
    if m:
        return f"{_venue(m.group(1))}, {m.group(2).strip()}"
    t = re.sub(r"(?i)\b(atp|wta|itf|challenger|ch|men|women|mens|womens|singles|doubles|open|cup|\d+)\b", " ", tournament or "")
    return re.sub(r"\s+", " ", t).strip(" -,")


def _surface(s: str) -> str:
    s = (s or "").lower()
    return "clay" if "clay" in s else "grass" if "grass" in s else "hard"


def team_event(tournament: str) -> bool:
    t = (tournament or "").lower()
    return any(k in t for k in TEAM_EVENTS)


def to_match(m: dict) -> dict | None:
    """A Live Tennis API match → the row format ESPN matches use (ids prefixed so they never clash)."""
    if m.get("is_doubles"):
        return None
    pl = m.get("players") or {}
    p1, p2 = pl.get("p1") or {}, pl.get("p2") or {}
    if not p1.get("name") or not p2.get("name") or not m.get("scheduled_time"):
        return None
    tour = (m.get("tour") or "").lower()
    gender = (m.get("gender") or "").lower()
    status = (m.get("status") or "").lower()
    when = pd.Timestamp(m["scheduled_time"])
    when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
    res = result_of(m)
    fmt = str(m.get("format") or "BO3").upper()
    return {
        "id": f"{PREFIX}{m.get('id')}", "event_id": f"{PREFIX}{m.get('tournament_id') or ''}",
        "event": m.get("tournament") or "", "tour": "wta" if (tour == "wta" or gender == "women") else "atp",
        "level": "challenger" if tour == "challenger" else ("team" if team_event(m.get("tournament")) else tour),
        "date": when, "venue": _venue(m.get("tournament") or ""), "round": m.get("round") or "",
        "best_of": 5 if fmt.endswith("5") else 3, "surface": _surface(m.get("surface")),
        "state": {"upcoming": "pre", "live": "in", "completed": "post"}.get(status, status),
        "status": status, "completed": status == "completed", "time_valid": True,
        "p1_id": f"{PREFIX}{p1.get('id')}", "p1": p1["name"], "p1_country": p1.get("country") or "", "p1_seed": None,
        "p1_entry": None, "p1_rank": p1.get("ranking"),
        "p2_id": f"{PREFIX}{p2.get('id')}", "p2": p2["name"], "p2_country": p2.get("country") or "", "p2_seed": None,
        "p2_entry": None, "p2_rank": p2.get("ranking"),
        "winner": res["winner"] if res else None, "score": res["score"] if res else "",
        "set_winners": res["set_winners"] if res else "", "retired": bool(res and res["retired"]),
        "walkover": bool(res and res.get("walkover")), "note": "",
        "_dob": {f"{PREFIX}{p1.get('id')}": p1.get("birthday"), f"{PREFIX}{p2.get('id')}": p2.get("birthday")},
        "_hand": {f"{PREFIX}{p1.get('id')}": p1.get("hand"), f"{PREFIX}{p2.get('id')}": p2.get("hand")},
    }


def result_of(m: dict) -> dict | None:
    """Final result of a finished match (None if not finished): set winners from the games, the winner, and
    retirements / walkovers (a winner without enough sets)."""
    status = (m.get("status") or "").lower()
    how = f"{m.get('outcome') or ''} {m.get('event_status') or ''}".lower()
    if "walk" in how or "w/o" in how:
        return {"winner": m.get("winner"), "set_winners": "", "score": "", "retired": False, "walkover": True, "void": True,
                "void_reason": "walkover"}
    if status == "cancelled" or "cancel" in how:
        return {"winner": None, "set_winners": "", "score": "", "retired": False, "walkover": True, "void": True,
                "void_reason": "cancelled"}
    if status != "completed":
        return None
    games = ((m.get("score") or {}).get("games")) or []
    sets = list(zip(*games)) if len(games) == 2 else []
    done = [(a, b) for a, b in sets if a != b and (max(a, b) >= 6 or max(a, b) >= 10)]
    sw = "".join("1" if a > b else "2" for a, b in done)
    winner = m.get("winner")
    if winner not in (1, 2):
        w1, w2 = sw.count("1"), sw.count("2")
        winner = 1 if w1 > w2 else 2 if w2 > w1 else None
    need = 3 if str(m.get("format") or "").upper().endswith("5") else 2
    short = max(sw.count("1"), sw.count("2")) < need
    if winner is None or not sw:
        return {"winner": winner, "set_winners": "", "score": "", "retired": False, "walkover": True, "void": True,
                "void_reason": "walkover" if winner else "no result"}
    return {"winner": int(winner), "set_winners": sw, "score": " ".join(f"{a}-{b}" for a, b in sets),
            "retired": short or bool(m.get("withdrew")) or "retir" in how, "walkover": False, "void": False}


def upcoming(client: Client, log=print) -> pd.DataFrame:
    """Upcoming Challenger singles, plus team events (Hopman Cup, United Cup, …) listed under the ATP / WTA tours."""
    rows = []
    for tour, keep in (("challenger", lambda m: True), ("atp", lambda m: team_event(m.get("tournament"))),
                       ("wta", lambda m: team_event(m.get("tournament")))):
        offset = 0
        for _ in range(2):              # at most two pages of 200
            try:
                page = client.get("/matches", status="upcoming", tour=tour, limit=200, offset=offset)
            except Exception as e:  # noqa: BLE001
                log(f"  {SOURCE} {tour}: unavailable ({type(e).__name__}: {e})")
                break
            data = page.get("data") or []
            rows += [r for r in (to_match(m) for m in data if keep(m)) if r]
            meta = page.get("meta") or {}
            if not meta.get("has_more") or len(data) < 200:
                break
            offset += 200
    return pd.DataFrame(rows)


def lookup(client: Client, match_id: str) -> dict | None:
    """One match (finished or not) by our id ('lta:123')."""
    d = client.get(f"/matches/{match_id[len(PREFIX):]}")
    return d.get("data", d) if isinstance(d, dict) else None


def settle(pending: list[dict], client: Client, now: datetime, log=print) -> dict[str, dict]:
    """Results of sealed Challenger / team-event forecasts, oldest first, as many as today's budget allows."""
    out = {}
    due = sorted((r for r in pending if r["match_id"].startswith(PREFIX)
                  and now - datetime.fromisoformat(r["start_utc"]) > timedelta(hours=2)), key=lambda r: r["start_utc"])
    for r in due:
        if client.left <= 0:
            log(f"  {SOURCE}: daily budget used; {len(due) - len(out)} result(s) wait for tomorrow (or enter them by hand)")
            break
        try:
            m = lookup(client, r["match_id"])
        except Exception as e:  # noqa: BLE001
            log(f"  {SOURCE} {r['match_id']}: {type(e).__name__}: {e}")
            continue
        res = result_of(m or {})
        if res:
            out[r["match_id"]] = res
    return out
