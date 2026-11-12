"""More soccer games with odds from OddsPapi (oddspapi.io, free key ODDS_PAPI): youth (U19-U23), international and club
friendlies, reserves and lower divisions the other sources do not cover. Used after football-data.co.uk, ESPN and
The Odds API, only for games none of them lists. Its "Simulated Reality League" (computer-simulated games) and
esports are left out. OddsPapi has no scores: KickoffAPI settles these games (results_kickoff.py).

Odds: Pinnacle when it prices the game, else the median of the bookmakers with all three prices (Full Time Result,
market 101); over/under 2.5 (market 1010) when offered."""
from __future__ import annotations

import json
import os
import re
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.oddspapi.io/v4"
SOURCE = "oddspapi.io"
MEN, WOMEN = "O:", "W:o"
MAX_ODDS_CALLS = 150
FAKE = re.compile(r"simulated|\bsrl\b|e-?soccer|esports?|cyber|virtual|e-?football|fifa \d\d|\bvolta\b", re.I)
WOMEN_WORDS = re.compile(r"women|woman|ladies|femen|femin|frauen|femminil|damen|dames|\(w\)|\bw\b|wk-league|reina", re.I)
FILE = Path(__file__).resolve().parents[1] / "ledger" / "oddspapi_tournaments.json"


def token() -> str | None:
    return os.environ.get("ODDS_PAPI") or None


class Client:
    def __init__(self, key: str, base: str = API):
        self.key, self.base, self.calls = key, base, 0

    def get(self, path: str, **params):
        q = urllib.parse.urlencode({**{k: v for k, v in params.items() if v is not None}, "apiKey": self.key})
        req = urllib.request.Request(f"{self.base}{path}?{q}", headers={"User-Agent": "astro-football-research",
                                                                          "Accept": "application/json"})
        self.calls += 1
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())


def names() -> dict[str, str]:
    """tournament id → "Country: Tournament", saved by the cycle (for display names of O: / W:o divisions)."""
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def league_name(code: str) -> str | None:
    if code.startswith(MEN):
        return names().get(code[len(MEN):])
    if code.startswith(WOMEN):
        return names().get(code[len(WOMEN):])
    return None


def is_women(f: dict) -> bool:
    text = " ".join(str(f.get(k) or "") for k in ("tournamentName", "categoryName", "participant1Name", "participant2Name"))
    return bool(WOMEN_WORDS.search(text))


def is_fake(f: dict) -> bool:
    return bool(FAKE.search(f"{f.get('categoryName')} {f.get('tournamentName')}"))


def prices(odds: dict) -> tuple[list[float], str, float | None] | None:
    """([home, draw, away], source, p_over25) from an /odds answer."""
    books = odds.get("bookmakerOdds") or {}

    def outcome(mk, oid):
        try:
            pl = mk["outcomes"][oid]["players"]["0"]
            p = float(pl["price"])
            return p if p > 1.0 else None
        except (KeyError, TypeError, ValueError):
            return None
    trios, over = {}, []
    for slug, b in books.items():
        mk = (b.get("markets") or {}).get("101")
        if mk:
            t = [outcome(mk, "101"), outcome(mk, "102"), outcome(mk, "103")]
            if all(t):
                trios[slug] = t
        ou = (b.get("markets") or {}).get("1010")
        if ou:
            o, u = outcome(ou, "1010"), outcome(ou, "1011")
            if o and u:
                over.append((1 / o) / (1 / o + 1 / u))
    if not trios:
        return None
    p_over = statistics.median(over) if over else None
    if "pinnacle" in trios:
        return trios["pinnacle"], f"{SOURCE} Pinnacle", p_over
    med = [round(statistics.median(t[i] for t in trios.values()), 3) for i in range(3)]
    return med, f"{SOURCE}, median of {len(trios)} bookmakers", p_over


def extra_fixtures(primary: list[dict], now: datetime, horizon_days: float, match_key, local_date, ledger_preds: list[dict],
                   venue_of, client: Client | None = None, log=print, women: bool = False, same_game=None) -> list[dict]:
    """Games with odds no other source lists, in the form of live.parse_fixtures."""
    if client is None:
        if not token():
            log("oddspapi.io: set ODDS_PAPI for youth games, friendlies, reserves and lower divisions")
            return []
        client = Client(token())
    until = now + timedelta(days=horizon_days)
    try:
        fx = client.get("/fixtures", sportId=10, hasOdds="true", **{"from": now.date().isoformat(), "to": until.date().isoformat()})
    except Exception as e:  # noqa: BLE001
        log(f"oddspapi.io unavailable: {type(e).__name__}: {e}")
        return []
    tn = names()
    out, skipped, fakes = [], [], 0
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    others = list(primary) + list(ledger_preds)
    for f in fx:
        if is_fake(f):
            fakes += 1
            continue
        if is_women(f) != women or (f.get("statusName") or "") not in ("Pre-Game", "Not Started", "NotStarted"):
            continue
        try:
            ko = datetime.fromisoformat(f["startTime"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if not (now < ko <= until):
            continue
        h, a = (f.get("participant1Name") or "").strip(), (f.get("participant2Name") or "").strip()
        if not h or not a:
            continue
        tid = str(f.get("tournamentId"))
        tn[tid] = f"{f.get('categoryName')}: {f.get('tournamentName')}"
        div = (WOMEN if women else MEN) + tid
        key = match_key(div, local_date(ko.isoformat()), h, a)
        if key in have:
            continue
        if same_game and any(same_game(h, a, ko.isoformat(), o["home"], o["away"], o["kickoff_utc"]) for o in others):
            continue                         # another source has the game already
        if client.calls >= MAX_ODDS_CALLS:
            skipped.append(f"{h} v {a}: odds request budget for this run used")
            continue
        try:
            got = prices(client.get("/odds", fixtureId=f["fixtureId"]))
            time.sleep(0.12)                  # 10 odds requests a second at most
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{h} v {a}: odds unavailable ({type(e).__name__})")
            continue
        if not got:
            skipped.append(f"{h} v {a}: no match-result odds")
            continue
        odds, book, p_over = got
        loc = venue_of(h, division=div, hint=None) if venue_of else None
        if not loc:
            skipped.append(f"{h} v {a} ({tn[tid]}): home ground not found")
            continue
        fxd = {"match_key": key, "division": div, "league": tn[tid], "home": h, "away": a, "kickoff_utc": ko.isoformat(),
               "odds": {"home": odds[0], "draw": odds[1], "away": odds[2]}, "odds_source": book, "p_over25": p_over,
               "venue_lat": loc[0], "venue_lon": loc[1], "venue_source": loc[2]}
        out.append(fxd)
        others.append(fxd)
        have.add(key)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps({**names(), **tn}, indent=0, sort_keys=True, ensure_ascii=False))
    except OSError:
        pass
    per = {}
    for x in out:
        per[x["league"]] = per.get(x["league"], 0) + 1
    log(f"oddspapi.io: {len(out)} extra fixture(s) ({client.calls} requests; {fakes} simulated games left out): "
        + ", ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda kv: -kv[1])))
    for s in skipped[:40]:
        log("  skipped:", s)
    return out
