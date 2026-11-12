"""Tennis odds from The Odds API (free key, the same ODDS_API_KEY secret as soccer).

It prices about 50 tournaments (Grand Slams, ATP Masters 1000, WTA 1000, the Finals and some 500s), not the
smaller events. Finding which tournaments and matches are listed costs nothing; buying a tournament's odds
costs one credit, so: only when one of our upcoming matches is listed, at most every ODDS_EVERY_H hours per
tournament, and never below RESERVE credits (left for soccer)."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .. import fixtures2

ODDS_EVERY_H = 12
RESERVE = 150
SOURCE = "the-odds-api.com"


def _norm(name: str) -> list[str]:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return [w for w in re.split(r"[^a-z]+", s) if w]


def same_player(a: str, b: str) -> bool:
    """Same surname (last word, or a long surname word shared) and the same first name (or initial)."""
    wa, wb = _norm(a), _norm(b)
    if not wa or not wb:
        return False
    # the same surname: the last word, or a long surname word shared ("Bassols Ribera" / "Ribera Bassols"); a
    # shared first name is not enough ("Zsombor Velcz" is not "Zsombor Piros")
    if wa[-1] != wb[-1] and not ({w for w in wa[1:] if len(w) > 3} & {w for w in wb[1:] if len(w) > 3}):
        return False
    fa, fb = wa[0], wb[0]
    if len(fa) > 1 and len(fb) > 1:          # full first names must agree (the Pliskova twins)
        return fa.startswith(fb) or fb.startswith(fa)
    return fa[0] == fb[0]


def _prices(ev: dict, home: str, away: str) -> tuple[float, float, str] | None:
    rows = []
    for b in ev.get("bookmakers", []):
        for m in b.get("markets", []):
            if m.get("key") == "h2h":
                px = {o["name"]: float(o["price"]) for o in m.get("outcomes", [])}
                if px.get(home, 0) > 1 and px.get(away, 0) > 1:
                    rows.append((px[home], px[away]))
    if not rows:
        return None
    return (sum(r[0] for r in rows) / len(rows), sum(r[1] for r in rows) / len(rows),
            f"{SOURCE}, average of {len(rows)} bookmaker{'s' if len(rows) > 1 else ''}")


def fetch(upcoming: list[dict], now: datetime, ledger: Path, client=None, log=print) -> dict[str, dict]:
    """Odds for our upcoming matches: {match_id: {"a": odds of player 1, "b": odds of player 2, "source"}}."""
    if client is None:
        key = fixtures2.token()
        if not key:
            log("tennis odds: no ODDS_API_KEY; forecasts go without odds")
            return {}
        client = fixtures2.Client(key)
    state_path = ledger / "odds_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    bought, cache = state.setdefault("bought", {}), state.setdefault("events", {})
    try:
        sports = [s for s in client.get("/sports") if s.get("group") == "Tennis" and s.get("active")]
    except Exception as e:  # noqa: BLE001
        log(f"tennis odds: unavailable ({type(e).__name__}: {e})")
        return {}
    out = {}
    for s in sports:
        key = s["key"]
        try:
            events = client.get(f"/sports/{key}/events")           # free
        except Exception as e:  # noqa: BLE001
            log(f"  {key}: events unavailable ({e})")
            continue
        pairs = []
        for ev in events:
            for m in upcoming:
                if ((same_player(m["p1"], ev["home_team"]) and same_player(m["p2"], ev["away_team"]))
                        or (same_player(m["p1"], ev["away_team"]) and same_player(m["p2"], ev["home_team"]))):
                    pairs.append((m, ev))
        if not pairs:
            continue
        last = bought.get(key)
        fresh = last and now - datetime.fromisoformat(last) < timedelta(hours=ODDS_EVERY_H)
        if not fresh or any(ev["id"] not in cache for _, ev in pairs):
            if fresh:
                pass
            elif client.remaining is not None and client.remaining < RESERVE:
                log(f"tennis odds: only {client.remaining:g} credits left; keeping them for soccer")
                break
            else:
                try:
                    for ev in client.get(f"/sports/{key}/odds", regions="eu", markets="h2h", oddsFormat="decimal"):
                        pr = _prices(ev, ev["home_team"], ev["away_team"])
                        if pr:
                            cache[ev["id"]] = {"home": ev["home_team"], "away": ev["away_team"], "home_odds": pr[0],
                                               "away_odds": pr[1], "source": pr[2], "at": now.isoformat(timespec="seconds")}
                    bought[key] = now.isoformat(timespec="seconds")
                except Exception as e:  # noqa: BLE001
                    log(f"  {key}: odds unavailable ({type(e).__name__}: {e})")
                    continue
        for m, ev in pairs:
            c = cache.get(ev["id"])
            if not c:
                continue
            a_home = same_player(m["p1"], c["home"])
            out[m["id"]] = {"a": c["home_odds"] if a_home else c["away_odds"], "b": c["away_odds"] if a_home else c["home_odds"],
                            "source": c["source"], "at": c["at"], "sport": key}
    # forget events older than a week
    cut = (now - timedelta(days=7)).isoformat()
    state["events"] = {k: v for k, v in cache.items() if v.get("at", "") >= cut}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    rem = f"; {client.remaining:g} credits left" if client.remaining is not None else ""
    log(f"tennis odds: {len(out)} match(es) priced from {len(sports)} listed tournament(s){rem}")
    return out
