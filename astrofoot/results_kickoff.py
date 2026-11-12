"""Results from KickoffAPI (kickoffapi.com, free key KICKOFF_API: 100 requests a day) for games none of the other
sources settles, chiefly OddsPapi's. One request per day of games; full-time results only (after extra time or
penalties the 90-minute score is not given, so those are left to the other sources or void)."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

from .results2 import pair

API = "https://api.kickoffapi.com/api/v2"
SOURCE = "kickoffapi.com"
FINAL = {"FT"}


def token() -> str | None:
    return os.environ.get("KICKOFF_API") or None


def fetch_day(day: str, key: str) -> list[dict]:
    out, cursor = [], None
    for _ in range(5):
        q = {"date": day, **({"cursor": cursor} if cursor else {})}
        req = urllib.request.Request(f"{API}/fixtures?{urllib.parse.urlencode(q)}",
                                     headers={"x-api-key": key, "Accept": "application/json", "User-Agent": "astro-football-research"})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        out += d.get("data") or []
        cursor = (d.get("meta") or {}).get("nextCursor")
        if not cursor:
            break
    return out


def normalise(rows: list[dict]) -> list[dict]:
    out = []
    for m in rows:
        if ((m.get("status") or {}).get("short") or "") not in FINAL:
            continue
        sc = m.get("score") or {}
        if sc.get("home") is None or sc.get("away") is None:
            continue
        out.append({"utc": m.get("date"), "home": [(m.get("home") or {}).get("name") or ""],
                    "away": [(m.get("away") or {}).get("name") or ""], "goals_home": int(sc["home"]),
                    "goals_away": int(sc["away"]), "league": (m.get("league") or {}).get("name")})
    return out


def match_results(pending: list[dict], key: str | None = None, fetch=fetch_day, log=print) -> dict[str, dict]:
    key = key or token()
    if not key or not pending:
        return {}
    days = sorted({datetime.fromisoformat(r["kickoff_utc"]).date().isoformat() for r in pending})
    games = []
    for d in days[-6:]:                     # the most recent six days (each one request)
        try:
            games += normalise(fetch(d, key))
        except Exception as e:  # noqa: BLE001
            log(f"kickoffapi.com {d}: unavailable ({type(e).__name__}: {e})")
    divs = {r["division"] for r in pending}
    cands = [{**g, "division": dv} for g in games for dv in divs]
    found, notes = pair(pending, cands, SOURCE)
    log(f"kickoffapi.com: {len(games)} finished game(s) over {len(days[-6:])} day(s); {len(found)} of {len(pending)} pending found")
    for n in notes[:20]:
        log("  unmatched:", n)
    return found
