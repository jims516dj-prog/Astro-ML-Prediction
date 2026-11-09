"""Second fixtures-and-odds source: The Odds API (the-odds-api.com, free plan, personal key).

football-data.co.uk (the primary) refreshes its fixtures list about twice a week, so games announced in
between were missed. This source fills those gaps, conservatively:

- Upcoming games are listed per league for free; odds cost one credit per league request (free plan:
  500 a month). A league's odds are bought only when it has a game within ODDS_LEAD_HOURS that neither
  the primary lists nor the ledger has forecast, and at most once per MIN_HOURS_BETWEEN per league.
- Team names are translated to football-data.co.uk's spelling (from the league's current-season results
  file and earlier forecasts), so venues resolve and the match key is the same one the primary will use
  for the fixture and its result. A name that cannot be paired confidently skips the game.
- Odds: Bet365 if offered (the training data's bookmaker), otherwise the average over the bookmakers
  offered, like football-data.co.uk's "Avg" columns. The forecast records which.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .dataset import EUROPEAN, LEAGUE_NAMES, MULTI_CLUB, NO_PRIMARY
from .results2 import similarity

API = "https://api.the-odds-api.com/v4"
SOURCE = "the-odds-api.com"
ODDS_LEAD_HOURS = 30
MIN_HOURS_BETWEEN = 20
MIN_CREDITS_LEFT = 25
SPORT_DIV = {
    "soccer_epl": "E0", "soccer_efl_champ": "E1", "soccer_england_league1": "E2", "soccer_england_league2": "E3",
    "soccer_spl": "SC0", "soccer_germany_bundesliga": "D1", "soccer_germany_bundesliga2": "D2",
    "soccer_italy_serie_a": "I1", "soccer_italy_serie_b": "I2", "soccer_spain_la_liga": "SP1",
    "soccer_spain_segunda_division": "SP2", "soccer_france_ligue_one": "F1", "soccer_france_ligue_two": "F2",
    "soccer_netherlands_eredivisie": "N1", "soccer_belgium_first_div": "B1", "soccer_portugal_primeira_liga": "P1",
    "soccer_turkey_super_league": "T1", "soccer_greece_super_league": "G1",
    "soccer_argentina_primera_division": "ARG", "soccer_austria_bundesliga": "AUT",
    "soccer_brazil_campeonato": "BRA", "soccer_china_superleague": "CHN", "soccer_denmark_superliga": "DEN",
    "soccer_finland_veikkausliiga": "FIN", "soccer_league_of_ireland": "IRL", "soccer_japan_j_league": "JAP",
    "soccer_mexico_ligamx": "MEX", "soccer_norway_eliteserien": "NOR", "soccer_poland_ekstraklasa": "POL",
    "soccer_russia_premier_league": "RUS", "soccer_switzerland_superleague": "SUI",
    "soccer_sweden_allsvenskan": "SWE", "soccer_usa_mls": "USA",
    "soccer_uefa_champs_league": "UCL", "soccer_uefa_europa_league": "UEL",
    "soccer_uefa_europa_conference_league": "UECL",
    "soccer_australia_aleague": "AUS", "soccer_brazil_serie_b": "BRA2", "soccer_chile_campeonato": "CHI",
    "soccer_conmebol_copa_libertadores": "LIB", "soccer_conmebol_copa_sudamericana": "SUD",
    "soccer_england_efl_cup": "EFLC", "soccer_fa_cup": "FAC", "soccer_germany_dfb_pokal": "DFB",
    "soccer_spain_copa_del_rey": "CDR",
    "soccer_korea_kleague1": "KOR", "soccer_saudi_arabia_pro_league": "KSA", "soccer_africa_cup_of_nations": "AFCON",
    "soccer_germany_liga3": "D3", "soccer_sweden_superettan": "SWE2", "soccer_france_coupe_de_france": "CDF",
    "soccer_italy_coppa_italia": "CIT",
}


def token() -> str | None:
    return os.environ.get("ODDS_API_KEY") or None


class Client:
    def __init__(self, key: str, base: str = API):
        self.key, self.base, self.remaining = key, base, None

    def get(self, path: str, **params):
        q = urllib.parse.urlencode({"apiKey": self.key, **params})
        req = urllib.request.Request(f"{self.base}{path}?{q}", headers={"User-Agent": "astro-football-research"})
        with urllib.request.urlopen(req, timeout=30) as r:
            rem = r.headers.get("x-requests-remaining")
            if rem is not None:
                self.remaining = float(rem)
            return json.loads(r.read())


# ----------------------------------------------------------------------------- team names
# Words many clubs share: two names agreeing only on these are not the same club ("Leicester City" / "Man City")
GENERIC = {"city", "united", "town", "county", "athletic", "atletico", "rovers", "wanderers", "albion", "real",
           "sporting", "club", "deportivo", "deportes", "racing", "olympic", "olympique", "dynamo", "dinamo", "fc",
           "sc", "ac", "sport", "sports", "football", "calcio", "stade", "borough", "rangers", "villa", "palace",
           "hotspur", "orient", "argyle", "alexandra", "stanley", "vale", "academy"}


def _distinctive_overlap(a: str, b: str) -> bool:
    from .results2 import _tokens
    return bool((_tokens(a) & _tokens(b)) - GENERIC)


def canonical_name(name: str, known: set[str]) -> str | None:
    """football-data.co.uk spelling of `name`, or None when no single known team is a clear match. The two names
    must share a distinctive word, not only a generic one like "City" or "United"."""
    if name in known:
        return name
    scored = sorted(((similarity(name, k), k) for k in known if _distinctive_overlap(name, k)), reverse=True)
    if not scored or scored[0][0] < 0.6:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.15:
        return None
    return scored[0][1]


def european_name(name: str, known: set[str]) -> str | None:
    """Stricter pairing for European ties, where clubs from everywhere meet: every word of the API's name
    must be in our club's name (after expanding abbreviations), so "Manchester United" → "Man United" and
    "AC Milan" → "Milan", but "Red Star Belgrade", "Lincoln Red Imps" or "Inter Club d'Escaldes" are not
    taken for Red Star, Lincoln or Inter. Exactly one such club must exist."""
    from .results2 import _tokens
    if name in known:
        return name
    t = _tokens(name)
    if not t:
        return None
    hits = [k for k in known if t <= _tokens(k)]
    return hits[0] if len(hits) == 1 else None


def known_teams(div: str, now: datetime, fetch_csv, results_url, ledger_preds: list[dict]) -> set[str]:
    """Team names football-data.co.uk uses in a division this season."""
    names = {n for r in ledger_preds if r["division"] == div for n in (r["home"], r["away"])}
    try:
        df = fetch_csv(results_url(div, now))
        if "Date" in df:
            dates = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df = df[dates >= pd.Timestamp(now.date()) - pd.Timedelta(days=330)]
        for col in ("HomeTeam", "AwayTeam"):
            if col in df:
                names |= {str(x).strip() for x in df[col].dropna()}
    except Exception:  # noqa: BLE001 - fall back to names already seen in the ledger
        pass
    return names


# ----------------------------------------------------------------------------- odds
def best_odds(event: dict, home: str, away: str) -> tuple[list[float], str] | None:
    """[home, draw, away] decimal odds: Bet365 if offered, else the average over bookmakers."""
    rows = {}
    for b in event.get("bookmakers", []):
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            px = {o["name"]: float(o["price"]) for o in m.get("outcomes", [])}
            trio = [px.get(home), px.get("Draw"), px.get(away)]
            if all(p and p > 1.0 for p in trio):
                rows[b.get("key")] = trio
    if not rows:
        return None
    if "bet365" in rows:
        return rows["bet365"], "Bet365"
    avg = [sum(r[i] for r in rows.values()) / len(rows) for i in range(3)]
    return avg, f"average of {len(rows)} bookmakers"


def over25(event: dict) -> float | None:
    """De-vigged P(over 2.5) from the bookmakers' totals market (average over books quoting the 2.5 line)."""
    ps = []
    for b in event.get("bookmakers", []):
        for m in b.get("markets", []):
            if m.get("key") != "totals":
                continue
            px = {o["name"].lower(): float(o["price"]) for o in m.get("outcomes", []) if float(o.get("point", 0)) == 2.5}
            if px.get("over", 0) > 1 and px.get("under", 0) > 1:
                ps.append((1 / px["over"]) / (1 / px["over"] + 1 / px["under"]))
    return sum(ps) / len(ps) if ps else None


# ----------------------------------------------------------------------------- main entry
def extra_fixtures(primary: list[dict], now: datetime, horizon_days: float, ledger: Path, client: Client,
                   fetch_csv, results_url, match_key, local_date, ledger_preds: list[dict],
                   log=print, venue_of=None, european_pool: set[str] | None = None) -> list[dict]:
    """venue_of(team) -> (lat, lon, source) | None locates a European home team's ground; european_pool is the
    set of football-data.co.uk team names to translate European entrants to (clubs outside it keep the
    API's name). European games already forecast (ledger_preds should exclude voided ones) are recognised by
    competition, kickoff and either club's name, so a spelling change never forecasts a game twice."""
    from .results2 import similarity
    euro_slots = [(r["division"], r["kickoff_utc"][:16], r["home"], r["away"]) for r in ledger_preds
                  if r["division"] in NO_PRIMARY]

    def euro_done(div, ko, h, a):
        k = ko.isoformat()[:16]
        return any(d == div and t == k and max(similarity(h, x), similarity(a, y)) >= 0.6
                   for d, t, x, y in euro_slots)
    """Fixtures (with odds) that the primary does not list, in the same form as live.parse_fixtures."""
    state_path = ledger / "odds_api_state.json"
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    # a team the primary already lists in that league on that day: the primary's fixture wins
    busy = {(f["division"], f["kickoff_utc"][:10], t) for f in primary for t in (f["home"], f["away"])}
    try:
        active = {s["key"] for s in client.get("/sports") if s.get("active")}
    except Exception as e:  # noqa: BLE001
        log(f"the-odds-api.com unavailable: {type(e).__name__}: {e}")
        return []
    out, bought, skipped = [], [], []
    for sport, div in SPORT_DIV.items():
        if sport not in active:
            continue
        try:
            events = client.get(f"/sports/{sport}/events")
        except Exception as e:  # noqa: BLE001
            log(f"  {div}: events unavailable ({type(e).__name__})")
            continue
        soon = []
        for ev in events:
            ko = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if now < ko <= now + timedelta(hours=min(ODDS_LEAD_HOURS, horizon_days * 24)):
                soon.append((ko, ev))
        if not soon:
            continue
        euro = div in NO_PRIMARY              # no football-data.co.uk file: own names, ground looked up
        if div in MULTI_CLUB:
            known = european_pool or set()
        elif euro:
            known = {n for r in ledger_preds if r["division"] == div for n in (r["home"], r["away"])}
        else:
            known = known_teams(div, now, fetch_csv, results_url, ledger_preds)
        todo = []
        for ko, ev in soon:
            if div in MULTI_CLUB:   # clubs from outside our leagues keep the API's spelling
                h = european_name(ev["home_team"], known) or ev["home_team"]
                a = european_name(ev["away_team"], known) or ev["away_team"]
            elif euro:              # a league only the secondary sources cover: earlier spelling, else the API's
                h = canonical_name(ev["home_team"], known) or ev["home_team"]
                a = canonical_name(ev["away_team"], known) or ev["away_team"]
            else:
                h, a = canonical_name(ev["home_team"], known), canonical_name(ev["away_team"], known)
            if not h or not a or h == a:
                skipped.append(f"{ev['home_team']} v {ev['away_team']} ({div}): team name not recognised")
                continue
            key = match_key(div, local_date(ko), h, a)
            if euro and euro_done(div, ko, h, a):
                continue
            day = ko.isoformat()[:10]
            if key in have or (div, day, h) in busy or (div, day, a) in busy:
                continue
            todo.append((ko, ev, h, a, key))
        if not todo:
            continue
        last = state.get(sport)
        if last and now - datetime.fromisoformat(last) < timedelta(hours=MIN_HOURS_BETWEEN):
            continue
        if client.remaining is not None and client.remaining < MIN_CREDITS_LEFT:
            log(f"the-odds-api.com: only {client.remaining:g} credits left this month; not buying more odds")
            break
        try:
            # European nights: also the totals market (one more credit) so goal predictions have a price
            priced = {e["id"]: e for e in client.get(f"/sports/{sport}/odds", regions="uk,eu" if div in
                                                     ("E0", "E1", "E2", "E3", "SC0") else "eu",
                                                     markets="h2h,totals" if div in NO_PRIMARY else "h2h",
                                                     oddsFormat="decimal")}
        except Exception as e:  # noqa: BLE001
            log(f"  {div}: odds unavailable ({type(e).__name__}: {e})")
            continue
        state[sport] = now.isoformat(timespec="seconds")
        bought.append(div)
        for ko, ev, h, a, key in todo:
            got = best_odds(priced.get(ev["id"], {}), ev["home_team"], ev["away_team"])
            if not got:
                skipped.append(f"{h} v {a} ({div}): no odds offered yet")
                continue
            odds, book = got
            fx = {"match_key": key, "division": div, "league": LEAGUE_NAMES.get(div, div),
                  "home": h, "away": a, "kickoff_utc": ko.isoformat(),
                  "odds": {"home": odds[0], "draw": odds[1], "away": odds[2]},
                  "odds_source": f"{SOURCE} {book}", "p_over25": over25(priced.get(ev["id"], {})) if euro else None}
            if euro:
                loc = venue_of(h, division=div) if venue_of else None
                if not loc:
                    skipped.append(f"{h} v {a} ({div}): home ground not found")
                    continue
                fx.update(venue_lat=loc[0], venue_lon=loc[1], venue_source=loc[2])
            out.append(fx)
            have.add(key)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    rem = f"; {client.remaining:g} credits left this month" if client.remaining is not None else ""
    log(f"the-odds-api.com: {len(out)} extra fixture(s); odds bought for {', '.join(bought) or 'no league'}{rem}")
    for s in skipped:
        log("  skipped:", s)
    return out


# ----------------------------------------------------------------------------- results
SCORES_EVERY_HOURS = 12


def scores_results(pending: list[dict], now: datetime, ledger: Path, client: Client, log=print) -> dict[str, dict]:
    """Results for competitions only The Odds API covers (no ESPN or football-data.org feed): its /scores endpoint
    (2 credits a call: completed games of the last 3 days), at most every SCORES_EVERY_HOURS per competition and only
    while a forecast there is waiting for its result."""
    from .results2 import pair
    from .results_espn import slug_of
    state_path = ledger / "odds_api_state.json"
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    sport_of = {d: k for k, d in SPORT_DIV.items()}
    by_div: dict[str, list[dict]] = {}
    for r in pending:
        if r["division"] in sport_of and r["division"] in NO_PRIMARY and not slug_of(r["division"]):
            by_div.setdefault(r["division"], []).append(r)
    found = {}
    for div, recs in sorted(by_div.items()):
        sport = sport_of[div]
        last = state.get("scores:" + sport)
        if last and now - datetime.fromisoformat(last) < timedelta(hours=SCORES_EVERY_HOURS):
            continue
        try:
            games = client.get(f"/sports/{sport}/scores", daysFrom=3)
        except Exception as e:  # noqa: BLE001
            log(f"  the-odds-api.com scores {div}: unavailable ({type(e).__name__})")
            continue
        state["scores:" + sport] = now.isoformat(timespec="seconds")
        norm = []
        for g in games:
            if not g.get("completed"):
                continue
            sc = {x.get("name"): x.get("score") for x in (g.get("scores") or [])}
            try:
                gh, ga = int(sc[g["home_team"]]), int(sc[g["away_team"]])
            except (KeyError, TypeError, ValueError):
                continue
            norm.append({"division": div, "utc": g["commence_time"], "home": [g["home_team"]], "away": [g["away_team"]],
                         "goals_home": gh, "goals_away": ga})
        f, _ = pair(recs, norm, SOURCE)
        found.update(f)
        log(f"the-odds-api.com scores {div}: {len(f)} of {len(recs)} pending result(s) found")
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    return found