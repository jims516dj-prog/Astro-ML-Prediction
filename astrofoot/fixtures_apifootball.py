"""More soccer games, with odds, stadiums and results, from API-Football (api-sports.io, free key API_FOOTBALL_KEY).

The free plan answers questions by date (not by season): `fixtures?date=` lists the day's games worldwide with their
stadium and city, and `odds?date=` (10 games a page) the pre-match prices of many of them. 100 requests a day, so each
cycle spends its share and the `status` call (free) keeps count. Used after football-data.co.uk, ESPN and The Odds
API, for games none of them lists: youth (U17-U23), club and international friendlies, reserve and lower leagues,
smaller countries, and women's games for the women's section.

Odds: Pinnacle when it prices the game, else the median of the bookmakers with all three prices ("Match Winner");
over/under 2.5 ("Goals Over/Under") when offered. Results: the score after 90 minutes (score.fulltime), so games
decided after extra time or penalties settle too."""
from __future__ import annotations

import json
import os
import re
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import geo, nations
from .results2 import pair

API = "https://v3.football.api-sports.io"
SOURCE = "api-football"
MEN, WOMEN = "A:", "W:a"
DAY_LIMIT = 100
RESERVE = 12                 # requests left for results and the other cycles of the day
CYCLES_PER_DAY = 3
MAX_ODDS_PAGES = 12          # per day of games
FILE = Path(__file__).resolve().parents[1] / "ledger" / "apifootball_leagues.json"
FAKE = re.compile(r"e-?soccer|esports?|cyber|virtual|e-?football|simulated", re.I)
WOMEN_WORDS = re.compile(r"women|woman|ladies|femen|femin|frauen|femminil|damen|dames|\bw-league\b|wk-league|"
                         r"\bnwsl\b|usl super league|damallsvenskan|toppserien|kvinde|reina|\bliga f\b|we league|"
                         r"\bwsl\b|\bw\b", re.I)
UPCOMING = {"NS"}
FINAL = {"FT", "AET", "PEN"}


def token() -> str | None:
    return os.environ.get("API_FOOTBALL_KEY") or None


class Client:
    """Counts the day's requests (from `status`, which is free) and caches answers for the run, so the men's and
    women's passes and the results look-up share them."""

    def __init__(self, key: str, base: str = API):
        self.key, self.base, self.calls = key, base, 0
        self.used_today: int | None = None
        self.cache: dict[str, dict] = {}

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(f"{self.base}/{path}", headers={"x-apisports-key": self.key,
                                                                    "Accept": "application/json",
                                                                    "User-Agent": "astro-football-research"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())

    def sync(self) -> int:
        if self.used_today is None:
            try:
                st = self._get("status").get("response") or {}
                self.used_today = int((st.get("requests") or {}).get("current") or 0)
            except Exception:  # noqa: BLE001
                self.used_today = 0
        return self.used_today

    def left(self) -> int:
        return DAY_LIMIT - self.sync() - self.calls

    def get(self, path: str, **params) -> dict:
        q = f"{path}?{urllib.parse.urlencode(params)}" if params else path
        if q in self.cache:
            return self.cache[q]
        if self.left() <= 0:
            raise RuntimeError("daily request limit reached")
        self.calls += 1
        d = self._get(q)
        err = d.get("errors")
        if err:
            raise RuntimeError(f"api-football: {err}")
        self.cache[q] = d
        return d


_CLIENT: Client | None = None


def client() -> Client | None:
    global _CLIENT
    if _CLIENT is None and token():
        _CLIENT = Client(token())
    return _CLIENT


def names() -> dict[str, str]:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def league_name(code: str) -> str | None:
    for p in (MEN, WOMEN):
        if code.startswith(p):
            return names().get(code[len(p):])
    return None


def is_women(f: dict) -> bool:
    lg = f.get("league") or {}
    teams = f.get("teams") or {}
    text = " ".join([str(lg.get("name") or ""), str((teams.get("home") or {}).get("name") or ""),
                     str((teams.get("away") or {}).get("name") or "")])
    return bool(WOMEN_WORDS.search(text))


def country_code(country: str | None) -> str | None:
    c = (country or "").replace("-", " ").strip()
    if not c or c == "World":
        return None
    return geo.COUNTRY_CODE.get(c) or nations.code_of(c) or {"Congo DR": "CD", "Bosnia": "BA", "Czech Republic": "CZ",
                                                              "Korea Republic": "KR", "USA": "US"}.get(c)


def ground(f: dict, team: str, div: str, venue_of):
    """(lat, lon, source): the stadium API-Football names (our tables, then its city), else our look-up of the home
    side (and its first team), else the main city of the league's country."""
    from .fixtures_oddspapi import SIDE
    lg, v = f.get("league") or {}, (f.get("fixture") or {}).get("venue") or {}
    country = (lg.get("country") or "").replace("-", " ")
    hint = {"name": v.get("name"), "city": v.get("city"), "country": country} if (v.get("name") or v.get("city")) else None
    tries = [team]
    while (b := SIDE.sub("", tries[-1]).strip()) and b != tries[-1]:
        tries.append(b)
    if venue_of:
        for i, n in enumerate(tries):
            try:
                loc = venue_of(n, division=div, hint=hint if i == 0 else None)
            except Exception:  # noqa: BLE001
                loc = None
            if loc:
                return loc if i == 0 else (loc[0], loc[1], f"{loc[2]} (first team's ground)")
    for n in tries:                                   # a national side: its country's main city
        nat = nations.code_of(n)
        got = nations.largest_city(nat, nations.HOME_NATION.get(n)) if nat else None
        if got:
            return got[0], got[1], f"national team: {got[2]} (main city)"
    code = country_code(lg.get("country"))
    if hint and hint.get("city") and code:
        city = re.split(r"[,(]", hint["city"])[0].strip()
        got = nations.largest_city(code, city)
        if got:
            return got[0], got[1], f"{v.get('name') or 'stadium'}, {got[2]} ({SOURCE})"
    got = nations.largest_city(code, nations.HOME_NATION.get(country)) if code else None
    return (got[0], got[1], f"{country}: {got[2]} (main city; ground unknown)") if got else None


def prices(entry: dict) -> tuple[list[float], str, float | None] | None:
    """([home, draw, away], source, p_over25) from one `odds` answer entry."""
    trios, over = {}, []
    for b in entry.get("bookmakers") or []:
        name = b.get("name") or str(b.get("id"))
        for bet in b.get("bets") or []:
            vals = {str(x.get("value")): x.get("odd") for x in bet.get("values") or []}
            try:
                if bet.get("name") == "Match Winner":
                    t = [float(vals["Home"]), float(vals["Draw"]), float(vals["Away"])]
                    if all(p > 1.0 for p in t):
                        trios[name] = t
                elif bet.get("name") == "Goals Over/Under":
                    o, u = float(vals["Over 2.5"]), float(vals["Under 2.5"])
                    if o > 1.0 and u > 1.0:
                        over.append((1 / o) / (1 / o + 1 / u))
            except (KeyError, TypeError, ValueError):
                continue
    if not trios:
        return None
    p_over = round(statistics.median(over), 4) if over else None
    if "Pinnacle" in trios:
        return trios["Pinnacle"], f"{SOURCE} Pinnacle", p_over
    med = [round(statistics.median(t[i] for t in trios.values()), 3) for i in range(3)]
    return med, f"{SOURCE}, median of {len(trios)} bookmakers", p_over


def day_odds(c: Client, day: str, pages: int) -> dict[int, dict]:
    out, total, page = {}, 1, 1
    while page <= min(total, pages):
        d = c.get("odds", date=day, page=page)
        total = int((d.get("paging") or {}).get("total") or 1)
        for e in d.get("response") or []:
            fid = (e.get("fixture") or {}).get("id")
            if fid is not None:
                out[fid] = e
        page += 1
    return out


def extra_fixtures(primary: list[dict], now: datetime, horizon_days: float, match_key, local_date, ledger_preds: list[dict],
                   venue_of, c: Client | None = None, log=print, women: bool = False, same_game=None) -> list[dict]:
    """Games with odds no other source lists, in the form of live.parse_fixtures (today and tomorrow, UTC)."""
    c = c or client()
    if c is None:
        log("api-football: set API_FOOTBALL_KEY for youth games, friendlies, reserves and smaller leagues")
        return []
    until = now + timedelta(days=min(horizon_days, 2))
    days = sorted({now.date().isoformat(), (now + timedelta(days=1)).date().isoformat()})
    fx, odds = [], {}
    # this cycle's share of the day's requests (the women's pass reuses the men's answers)
    share = max(0, (c.left() - RESERVE) // max(1, CYCLES_PER_DAY - now.hour // 8))
    pages = max(1, min(MAX_ODDS_PAGES, (share - len(days)) // max(1, len(days))))
    for d in days:
        try:
            fx += c.get("fixtures", date=d).get("response") or []
            odds.update(day_odds(c, d, pages))
        except Exception as e:  # noqa: BLE001
            log(f"api-football {d}: unavailable ({type(e).__name__}: {e})")
    tn = names()
    out, skipped, no_odds = [], [], 0
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    others = list(primary) + list(ledger_preds)
    for f in fx:
        lg, fi, tm = f.get("league") or {}, f.get("fixture") or {}, f.get("teams") or {}
        if FAKE.search(str(lg.get("name") or "")) or is_women(f) != women:
            continue
        if ((fi.get("status") or {}).get("short") or "") not in UPCOMING:
            continue
        try:
            ko = datetime.fromisoformat(str(fi["date"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        if not (now < ko <= until):
            continue
        h, a = ((tm.get("home") or {}).get("name") or "").strip(), ((tm.get("away") or {}).get("name") or "").strip()
        if not h or not a:
            continue
        lid = str(lg.get("id"))
        tn[lid] = f"{lg.get('country')}: {lg.get('name')}"
        div = (WOMEN if women else MEN) + lid
        key = match_key(div, local_date(ko.isoformat()), h, a)
        if key in have:
            continue
        if same_game and any(same_game(h, a, ko.isoformat(), o["home"], o["away"], o["kickoff_utc"]) for o in others):
            continue
        got = prices(odds[fi["id"]]) if fi.get("id") in odds else None
        if not got:
            no_odds += 1
            continue
        loc = ground(f, h, div, venue_of)
        if not loc:
            skipped.append(f"{h} v {a} ({tn[lid]}): home ground not found")
            continue
        o3, book, p_over = got
        fxd = {"match_key": key, "division": div, "league": tn[lid], "home": h, "away": a, "kickoff_utc": ko.isoformat(),
               "odds": {"home": o3[0], "draw": o3[1], "away": o3[2]}, "odds_source": book, "p_over25": p_over,
               "venue_lat": loc[0], "venue_lon": loc[1], "venue_source": loc[2]}
        out.append(fxd)
        others.append(fxd)
        have.add(key)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps({**names(), **tn}, indent=0, sort_keys=True, ensure_ascii=False))
    except OSError:
        pass
    per: dict[str, int] = {}
    for x in out:
        per[x["league"]] = per.get(x["league"], 0) + 1
    log(f"api-football: {len(out)} extra fixture(s) ({c.calls} requests this run, {c.left()} left today; "
        f"{no_odds} new game(s) without odds yet): " + ", ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda kv: -kv[1])))
    for s in skipped[:30]:
        log("  skipped:", s)
    return out


def normalise(rows: list[dict]) -> list[dict]:
    out = []
    for f in rows:
        fi, tm = f.get("fixture") or {}, f.get("teams") or {}
        if ((fi.get("status") or {}).get("short") or "") not in FINAL:
            continue
        ft = (f.get("score") or {}).get("fulltime") or {}
        if ft.get("home") is None or ft.get("away") is None:
            continue
        out.append({"utc": fi.get("date"), "home": [(tm.get("home") or {}).get("name") or ""],
                    "away": [(tm.get("away") or {}).get("name") or ""], "goals_home": int(ft["home"]),
                    "goals_away": int(ft["away"]), "league": (f.get("league") or {}).get("name")})
    return out


def match_results(pending: list[dict], c: Client | None = None, log=print) -> dict[str, dict]:
    """Scores after 90 minutes for pending games without a football-data.co.uk file (one request per day of games)."""
    c = c or client()
    if c is None or not pending:
        return {}
    days = sorted({datetime.fromisoformat(r["kickoff_utc"]).astimezone(timezone.utc).date().isoformat() for r in pending})
    games = []
    for d in days[-6:]:
        try:
            games += normalise(c.get("fixtures", date=d).get("response") or [])
        except Exception as e:  # noqa: BLE001
            log(f"api-football results {d}: unavailable ({type(e).__name__}: {e})")
    divs = {r["division"] for r in pending}
    found, notes = pair(pending, [{**g, "division": dv} for g in games for dv in divs], SOURCE)
    log(f"api-football: {len(games)} finished game(s) over {len(days[-6:])} day(s); {len(found)} of {len(pending)} pending found")
    for n in notes[:20]:
        log("  unmatched:", n)
    return found
