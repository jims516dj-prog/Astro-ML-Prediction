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

from . import nations

API = "https://api.oddspapi.io/v4"
SOURCE = "oddspapi.io"
MEN, WOMEN = "O:", "W:o"
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


SIDE = re.compile(r"\s+(Reserves?|Res\.?|Women|W|Ladies|Fem\.?|Femenino|Feminino|Frauen|Dames|II|III|B|2|3|"
                  r"U-?\d{2}|Under[- ]?\d{2}|Sub-?\d{2}|Youth|Academy)$", re.I)
COUNTRY_WORDS = re.compile(r"\s+(Amateur|Youth|Women|Cup|Cups)$", re.I)


def ground(f: dict, team: str, div: str, venue_of):
    """(lat, lon, source) for the home side: its own ground, else its first team's, else the main city of the
    country OddsPapi files the game under (good enough for the day and the venue's time zone; OddsPapi names no
    venue). International categories without a country have no fallback."""
    if venue_of:
        names = [team]
        base = team
        while (b := SIDE.sub("", base).strip()) and b != base:
            names.append(b)
            base = b
        for n in names:
            try:
                loc = venue_of(n, division=div, hint=None)
            except Exception:  # noqa: BLE001
                loc = None
            if loc:
                return loc if n == team else (loc[0], loc[1], f"{loc[2]} (first team's ground)")
    cat = COUNTRY_WORDS.sub("", (f.get("categoryName") or "").strip())
    code = nations.code_of(cat)
    got = nations.largest_city(code, nations.HOME_NATION.get(cat)) if code else None
    return (got[0], got[1], f"{cat}: {got[2]} (main city; ground unknown)") if got else None


AGE = re.compile(r"(?i)\b(?:U-?|Under[- ]?|Sub-?)(\d{2})\b")


def with_age(team: str, f: dict) -> str:
    """OddsPapi names youth sides like the senior ones ("England" in its "U21 Friendly Games"): add the age group,
    so that the game is never taken for (or forecast with the data of) the senior teams."""
    m = AGE.search(f"{f.get('tournamentName') or ''} {f.get('categoryName') or ''}")
    if not m or AGE.search(team):
        return team
    return f"{team} U{m.group(1)}"


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


USAGE = Path(__file__).resolve().parents[1] / "ledger" / "oddspapi_usage.json"
MONTH_LIMIT = 240            # the free plan: about 250 requests a month; a 429 answer means it is spent
BATCH = 5                    # tournaments per odds-by-tournaments request
_FX: dict[str, list] = {}    # the run's fixture list, shared by the men's and women's passes


def usage(today: str) -> dict:
    try:
        u = json.loads(USAGE.read_text())
    except (OSError, ValueError):
        u = {}
    if u.get("month") != today[:7]:
        u = {"month": today[:7], "used": 0}
    if u.get("day") != today:
        u.update(day=today, day_used=0)
    return u


def save_usage(u: dict) -> None:
    try:
        USAGE.parent.mkdir(parents=True, exist_ok=True)
        USAGE.write_text(json.dumps(u, sort_keys=True))
    except OSError:
        pass


def allowance(u: dict, today: str) -> int:
    """Requests this run may spend: the month's remainder spread evenly over its remaining days."""
    if u.get("blocked"):
        return 0
    d = datetime.fromisoformat(today)
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    days_left = (nxt - d).days
    return max(0, (MONTH_LIMIT - u["used"]) // days_left - u["day_used"])


def bulk_odds(client: Client, tids: list[str], log=print) -> tuple[dict[str, dict], bool]:
    """fixtureId -> odds entry for every fixture in these tournaments; (answers, quota_spent)."""
    out = {}
    d = client.get("/odds-by-tournaments", tournamentIds=",".join(tids), oddsFormat="decimal")
    rows = d.get("data", d) if isinstance(d, dict) else d
    if isinstance(rows, dict):
        rows = [{"fixtureId": k, **v} if isinstance(v, dict) else {} for k, v in rows.items()]
    for e in rows or []:
        if isinstance(e, dict) and e.get("fixtureId") is not None:
            out[str(e["fixtureId"])] = e
    return out, False


def extra_fixtures(primary: list[dict], now: datetime, horizon_days: float, match_key, local_date, ledger_preds: list[dict],
                   venue_of, client: Client | None = None, log=print, women: bool = False, same_game=None) -> list[dict]:
    """Games with odds no other source lists, in the form of live.parse_fixtures. Within the free plan's monthly
    quota: one fixture list per run, then odds for whole tournaments (most new games first)."""
    if client is None:
        if not token():
            log("oddspapi.io: set ODDS_PAPI for youth games, friendlies, reserves and lower divisions")
            return []
        client = Client(token())
    today = now.date().isoformat()
    u = usage(today)
    budget = allowance(u, today)
    until = now + timedelta(days=min(horizon_days, 2))
    fx = _FX.get(today)
    if fx is None:
        if budget < 2:
            log(f"oddspapi.io: monthly quota kept for later ({u['used']} of {MONTH_LIMIT} used this month"
                + ("; spent until the month ends" if u.get("blocked") else "") + ")")
            return []
        try:
            fx = client.get("/fixtures", sportId=10, hasOdds="true", **{"from": today, "to": until.date().isoformat()})
            err = None
        except Exception as e:  # noqa: BLE001
            err = e
        u["used"] += client.calls
        u["day_used"] += client.calls
        client.calls = 0
        if err is not None:
            if "429" in str(err):
                u.update(blocked=True, used=max(u["used"], MONTH_LIMIT))
            save_usage(u)
            log(f"oddspapi.io unavailable: {type(err).__name__}: {err}")
            return []
        _FX[today] = fx
        save_usage(u)
        budget = allowance(u, today)
    tn = names()
    skipped, fakes = [], 0
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    others = list(primary) + list(ledger_preds)
    cands: dict[str, list] = {}
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
        h, a = with_age(h, f), with_age(a, f)
        tid = str(f.get("tournamentId"))
        tn[tid] = f"{f.get('categoryName')}: {f.get('tournamentName')}"
        div = (WOMEN if women else MEN) + tid
        key = match_key(div, local_date(ko.isoformat()), h, a)
        if key in have:
            continue
        if same_game and any(same_game(h, a, ko.isoformat(), o["home"], o["away"], o["kickoff_utc"]) for o in others):
            continue                         # another source has the game already
        loc = ground(f, h, div, venue_of)
        if not loc:
            skipped.append(f"{h} v {a} ({tn[tid]}): home ground not found")
            continue
        cands.setdefault(tid, []).append((f, key, div, ko, h, a, loc))
    # the tournaments with the most new games first, BATCH per request, while the quota allows
    order = sorted(cands, key=lambda t: -len(cands[t]))
    odds: dict[str, dict] = {}
    asked = []
    batch = BATCH
    while order and budget > 0:
        part, order = order[:batch], order[batch:]
        try:
            got, _ = bulk_odds(client, part, log)
            odds.update(got)
            asked += part
            time.sleep(1.1)                   # the endpoint's cool-down
        except Exception as e:  # noqa: BLE001
            if "429" in str(e):
                u.update(blocked=True)
                break
            if batch > 1 and any(c in str(e) for c in ("400", "422")):
                order, batch = part + order, 1  # several tournaments per request refused: one at a time
                continue
            skipped.append(f"tournaments {','.join(part)}: odds unavailable ({type(e).__name__})")
        finally:
            u["used"] += client.calls
            u["day_used"] += client.calls
            budget -= client.calls
            client.calls = 0
    save_usage(u)
    out = []
    for tid, rows in cands.items():
        for f, key, div, ko, h, a, loc in rows:
            if tid not in asked:
                continue
            got = prices(odds[str(f["fixtureId"])]) if str(f.get("fixtureId")) in odds else None
            if not got:
                skipped.append(f"{h} v {a}: no match-result odds")
                continue
            o3, book, p_over = got
            fxd = {"match_key": key, "division": div, "league": tn[tid], "home": h, "away": a,
                   "kickoff_utc": ko.isoformat(), "odds": {"home": o3[0], "draw": o3[1], "away": o3[2]},
                   "odds_source": book, "p_over25": p_over, "venue_lat": loc[0], "venue_lon": loc[1],
                   "venue_source": loc[2]}
            out.append(fxd)
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps({**names(), **tn}, indent=0, sort_keys=True, ensure_ascii=False))
    except OSError:
        pass
    per = {}
    for x in out:
        per[x["league"]] = per.get(x["league"], 0) + 1
    left = sum(len(cands[t]) for t in cands if t not in asked)
    log(f"oddspapi.io: {len(out)} extra fixture(s) ({u['used']} of {MONTH_LIMIT} requests used this month; "
        f"{left} game(s) in {len(cands) - len(asked)} tournament(s) left for lack of quota; {fakes} simulated games "
        "left out): " + ", ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda kv: -kv[1])))
    for s_ in skipped[:30]:
        log("  skipped:", s_)
    return out
