"""Third fixtures-and-odds source: ESPN's public scoreboard (free, no key), with DraftKings odds.

Checked after football-data.co.uk and before The Odds API (which costs credits). It adds:
  - games in our leagues that football-data.co.uk has not listed yet;
  - leagues and cups football-data.co.uk does not cover (South America, Australia, Saudi Arabia, domestic cups,
    continental cups), forecast like the UEFA competitions: own names, ground looked up, results from ESPN.

A game is used only when ESPN shows home, draw and away odds (a forecast needs a market baseline). The
over/under 2.5 price is taken when ESPN's total line is 2.5. Names in our leagues are translated to
football-data.co.uk's spelling (or the game is skipped), as for The Odds API.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timedelta
from functools import lru_cache

from .config import ROOT
from .dataset import DISCOVERED, LEAGUE_NAMES, MULTI_CLUB, NO_PRIMARY
from .fixtures2 import canonical_name, european_name
from .results_espn import LEAGUE_SLUG

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues?limit=1000"
COMP_FILE = ROOT / "ledger" / "espn_competitions.json"
DISCOVER_EVERY_HOURS = 20
DISCOVER_DAYS = 4
# Checked from the start even before discovery has seen odds for them (ESPN prices a league around its match days)
SEEDS = {"bol.1": "Bolivian Liga Profesional", "ven.1": "Venezuelan Primera División", "crc.1": "Costa Rican Primera",
         "hon.1": "Honduran Liga Nacional", "gua.1": "Guatemalan Liga Nacional", "slv.1": "Salvadoran Primera",
         "pan.1": "Panamanian Liga", "can.1": "Canadian Premier League", "arg.2": "Argentine Primera Nacional",
         "mex.2": "Liga de Expansión MX", "chi.2": "Chilean Primera B", "col.2": "Colombian Primera B",
         "eng.trophy": "English EFL Trophy", "uefa.nations": "UEFA Nations League",
         # the Americas: cups and second tiers bookmakers price around match days
         "arg.copa": "Copa Argentina", "arg.3": "Argentine Primera B", "bra.copa_do_brazil": "Copa do Brasil",
         "chi.copa_chi": "Copa Chile", "col.copa": "Copa Colombia", "bol.copa": "Copa Bolivia",
         "uru.2": "Segunda División de Uruguay", "usa.usl.1": "USL Championship", "usa.usl.l1": "USL League One",
         "usa.open": "U.S. Open Cup", "conmebol.recopa": "CONMEBOL Recopa", "concacaf.leagues.cup": "Leagues Cup",
         "bra.camp.paulista": "Brazilian Campeonato Paulista", "bra.camp.carioca": "Brazilian Campeonato Carioca",
         "bra.camp.mineiro": "Brazilian Campeonato Mineiro", "bra.camp.gaucho": "Brazilian Campeonato Gaucho",
         "concacaf.nations.league": "Concacaf Nations League",
         # Oceania and the Middle East: the club competitions ESPN carries (the A-League and Saudi Pro League are mapped)
         "afc.champions": "AFC Champions League Elite", "afc.cup": "AFC Champions League Two",
         "ksa.kings.cup": "Saudi King's Cup"}
ACADEMY_CUPS = {"eng.trophy"}
# Youth, reserve and women's sides are left out (the models were trained on men's senior league football)
YOUTH = re.compile(r"\bU-?\d{2}\b|\bunder[- ]?\d{2}\b|women|femenin|féminin|frauen|ladies|\(w\)", re.I)
# The women's section (ledger/women): women's senior competitions, discovered like the men's
WOMEN_FILE = ROOT / "ledger" / "women" / "espn_competitions.json"
WOMEN_RE = re.compile(r"^[a-z]+\.w[a-z]|(^|\.)w(\.|$)|women|wom[ae]n|wsl|frauen|f[eé]min|femenil|damallsvenskan|"
                      r"\bliga f\b|ladies|nwsl", re.I)
YOUTH_COLLEGE = re.compile(r"youth|junior|olympic|ncaa|college|girls|\bu-?\d{2}\b|(^|\.)u\d+(\.|$)", re.I)
WOMEN_SEEDS = {"uefa.wchampions": "UEFA Women's Champions League", "eng.w.1": "English Women's Super League",
               "esp.w.1": "Spanish Liga F", "fra.w.1": "French Première Ligue", "ger.w.1": "German Frauen-Bundesliga",
               "ita.w.1": "Italian Serie A Women", "usa.nwsl": "NWSL", "mex.w.1": "Liga MX Femenil",
               "swe.w.1": "Swedish Damallsvenskan", "aus.w.1": "Australian A-League Women"}
YOUTH_ONLY = re.compile(r"\bU-?\d{2}\b|\bunder[- ]?\d{2}\b", re.I)
# A competition that is not men's senior football, by ESPN code or name (case-insensitive): women's ("w" codes such as
# uefa.wchampions, eng.w.1; Women's, Frauen, Féminine, Femenil, Damallsvenskan, Liga F, NWSL), youth, college, Olympic
NOT_MEN = re.compile(r"(^|\.)(w|u\d+)(\.|$)|^[a-z]+\.w[a-z]|women|wom[ae]n|wsl|frauen|f[eé]min|femenil|damallsvenskan|"
                     r"\bliga f\b|ladies|girls|youth|junior|olympic|ncaa|college|nwsl|\bu-?\d{2}\b", re.I)
SOURCE = "espn.com"
DAYS_AHEAD = 2                 # today and tomorrow (the cycle runs three times a day)


@lru_cache(maxsize=4)
def _comps(mtime: float) -> dict[str, str]:
    try:
        return json.loads(COMP_FILE.read_text()).get("competitions", {})
    except (OSError, ValueError):
        return {}


def discovered_names() -> dict[str, str]:
    """slug -> name of every competition discovery has seen with odds, plus the seeds (never women's, youth or
    college competitions, even if an older discovery remembered one)."""
    mtime = COMP_FILE.stat().st_mtime if COMP_FILE.exists() else 0.0
    return {k: v for k, v in {**SEEDS, **_comps(mtime)}.items() if not NOT_MEN.search(k) and not NOT_MEN.search(v)}


@lru_cache(maxsize=4)
def _women_comps(mtime: float) -> dict[str, str]:
    try:
        return json.loads(WOMEN_FILE.read_text()).get("competitions", {})
    except (OSError, ValueError):
        return {}


def women_names() -> dict[str, str]:
    """slug -> name of the women's competitions (discovered with odds, plus the seeds)."""
    mtime = WOMEN_FILE.stat().st_mtime if WOMEN_FILE.exists() else 0.0
    return {k: v for k, v in {**WOMEN_SEEDS, **_women_comps(mtime)}.items() if not YOUTH_COLLEGE.search(k + " " + v)}


def women_slugs() -> list[tuple[str, str]]:
    """(division code "W:<slug>", slug) of the women's competitions."""
    return [("W:" + slug, slug) for slug in sorted(women_names())]


def discovered_slugs() -> list[tuple[str, str]]:
    """(division code, slug) of the discovered competitions not already in our fixed map."""
    fixed = set(LEAGUE_SLUG.values())
    return [(DISCOVERED + slug, slug) for slug in sorted(discovered_names()) if slug not in fixed]


def discover(now: datetime, path=COMP_FILE, get=None, log=print, force: bool = False, women: bool = False) -> int:
    """Once a day: scan every men's competition ESPN lists and remember those with upcoming games that have home/
    draw/away odds. A competition stays remembered (odds come and go with match days). Returns how many it found
    this time (-1 when skipped)."""
    import re as _re
    get = get or (lambda url: json.loads(urllib.request.urlopen(urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (astro-football-research)"}), timeout=20).read()))
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        state = {}
    if not force and state.get("generated_at"):
        if (now - datetime.fromisoformat(state["generated_at"])).total_seconds() < DISCOVER_EVERY_HOURS * 3600:
            return -1
    try:
        items = get(CORE).get("items", [])
    except Exception as e:  # noqa: BLE001
        log(f"espn.com discovery: league list unavailable ({type(e).__name__})")
        return 0
    slugs = sorted({m.group(1) for it in items for m in [_re.search(r"/leagues/([^/?]+)", it.get("$ref", ""))] if m})
    if women:      # women's senior competitions only (no youth or college)
        wanted = lambda slug, name="": bool(WOMEN_RE.search(slug + " " + name)) and not YOUTH_COLLEGE.search(slug + " " + name)  # noqa: E731
    else:          # men's senior football only
        wanted = lambda slug, name="": not (NOT_MEN.search(slug) or NOT_MEN.search(name))  # noqa: E731
    # women's codes are not always marked in the slug: check every competition's name when looking for them
    slugs = [x for x in slugs if women or wanted(x)]
    comps = {k: v for k, v in state.get("competitions", {}).items() if wanted(k, v)}
    found = 0
    for slug in slugs:
        name, priced = "", 0
        if women:          # read the name once first; scan the days only for women's competitions
            try:
                name = (get(f"{API}/{slug}/scoreboard").get("leagues") or [{}])[0].get("name") or slug
            except Exception:  # noqa: BLE001
                continue
            if not wanted(slug, name):
                continue
        for k in range(DISCOVER_DAYS):
            try:
                d = get(f"{API}/{slug}/scoreboard?dates={(now + timedelta(days=k)):%Y%m%d}")
            except Exception:  # noqa: BLE001
                break
            name = name or ((d.get("leagues") or [{}])[0].get("name") or slug)
            for e in d.get("events", []):
                try:
                    priced += parse_event(e) is not None
                except Exception:  # noqa: BLE001
                    pass
        if priced and wanted(slug, name):
            comps[slug] = name
            found += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"generated_at": now.isoformat(timespec="seconds"), "competitions": comps},
                               indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    _comps.cache_clear()
    _women_comps.cache_clear()
    log(f"espn.com discovery{' (women)' if women else ''}: {found} competitions with odds now, {len(comps)} remembered")
    return found


def american_to_decimal(ml) -> float | None:
    try:
        v = float(str(ml).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return 1 + v / 100 if v > 0 else 1 + 100 / abs(v)


def _get(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (astro-football-research)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("events", [])


def fetch(slug: str, day) -> list[dict]:
    return _get(f"{API}/{slug}/scoreboard?dates={day:%Y%m%d}")      # ESPN refuses date ranges


def parse_event(ev: dict) -> dict | None:
    """ESPN event → {kickoff, home, away, odds [h, d, a], p_over25, venue {name, city, country}} or None."""
    if ((ev.get("status") or {}).get("type") or {}).get("state") != "pre":
        return None
    comp = (ev.get("competitions") or [{}])[0]
    side = {c.get("homeAway"): c for c in comp.get("competitors", [])}
    if "home" not in side or "away" not in side:
        return None
    odds = next((o for o in (comp.get("odds") or []) if isinstance(o, dict)), None)
    if not odds:                                     # no odds published yet (ESPN lists null)
        return None
    ml = odds.get("moneyline") or {}

    def price(side: str, old_key: str):
        """Closing (else opening) moneyline from the "moneyline" block; older payloads use homeTeamOdds etc."""
        blk = ml.get(side) or {}
        v = (blk.get("close") or {}).get("odds") or (blk.get("open") or {}).get("odds")
        if v is None:
            v = (odds.get(old_key) or {}).get("moneyLine")
        return american_to_decimal(v)
    h, d, a = price("home", "homeTeamOdds"), price("draw", "drawOdds"), price("away", "awayTeamOdds")
    if not (h and d and a and min(h, d, a) > 1):
        return None
    p_over = None
    tot = odds.get("total") or {}
    try:
        over, under = tot.get("over", {}).get("close") or {}, tot.get("under", {}).get("close") or {}
        if str(over.get("line", "")).lstrip("ou") == "2.5":
            o, u = american_to_decimal(over.get("odds")), american_to_decimal(under.get("odds"))
            if o and u:
                p_over = (1 / o) / (1 / o + 1 / u)
    except AttributeError:
        pass
    v = comp.get("venue") or {}
    name = lambda c: ((c.get("team") or {}).get("displayName") or "").strip()      # noqa: E731
    return {"kickoff": datetime.fromisoformat((comp.get("date") or ev["date"]).replace("Z", "+00:00")),
            "home": name(side["home"]), "away": name(side["away"]), "odds": [h, d, a], "p_over25": p_over,
            "book": (odds.get("provider") or {}).get("name") or "ESPN",
            "venue": {"name": v.get("fullName"), "city": (v.get("address") or {}).get("city"),
                      "country": (v.get("address") or {}).get("country")}}


def extra_fixtures(primary: list[dict], now: datetime, horizon_days: float, match_key, local_date,
                   ledger_preds: list[dict], known_of, multi_pool: set[str], venue_of, fetch=fetch,
                   log=print, senior_clubs: set[str] | None = None, competitions=None,
                   women: bool = False) -> list[dict]:
    """Fixtures (with odds) ESPN lists that `primary` does not, in the form of live.parse_fixtures.
    known_of(div) -> football-data.co.uk names for one of our leagues; multi_pool: names for cups/European ties."""
    busy = {(f["division"], f["kickoff_utc"][:10], t) for f in primary for t in (f["home"], f["away"])}
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    out, skipped, per, bad = [], [], {}, []
    comps = competitions if competitions is not None else sorted(LEAGUE_SLUG.items()) + discovered_slugs()
    youth = YOUTH_ONLY if women else YOUTH
    for div, slug in comps:
        known = None
        for k in range(DAYS_AHEAD):
            try:
                events = fetch(slug, (now + timedelta(days=k)).date())
            except Exception:  # noqa: BLE001 - unknown slug or no games: nothing to add
                continue
            for ev in events:
                try:
                    g = parse_event(ev)
                except Exception as e:  # noqa: BLE001 - one odd event never stops the rest
                    import traceback
                    bad.append(f"{slug}: {type(e).__name__} at {traceback.extract_tb(e.__traceback__)[-1].line}")
                    continue
                if g is None or not (now < g["kickoff"] <= now + timedelta(days=horizon_days)):
                    continue
                if youth.search(g["home"]) or youth.search(g["away"]):
                    continue
                if slug in ACADEMY_CUPS:
                    # only lower-league clubs enter these, plus top clubs' academy (U21) sides that ESPN may list
                    # under the senior name: a top-two-division club here is its academy side
                    senior = senior_clubs if senior_clubs is not None else known_of("E0") | known_of("E1")
                    if canonical_name(g["home"], senior) or canonical_name(g["away"], senior):
                        skipped.append(f"{g['home']} v {g['away']} ({div}): an academy side (top-two-division club)")
                        continue
                if div in MULTI_CLUB:
                    h = european_name(g["home"], multi_pool) or g["home"]
                    a = european_name(g["away"], multi_pool) or g["away"]
                elif div in NO_PRIMARY:
                    names = {n for r in ledger_preds if r["division"] == div for n in (r["home"], r["away"])}
                    h, a = canonical_name(g["home"], names) or g["home"], canonical_name(g["away"], names) or g["away"]
                else:
                    known = known if known is not None else known_of(div)
                    h, a = canonical_name(g["home"], known), canonical_name(g["away"], known)
                    if not h or not a or h == a:
                        skipped.append(f"{g['home']} v {g['away']} ({div}): team name not recognised")
                        continue
                day = g["kickoff"].isoformat()[:10]
                key = match_key(div, local_date(g["kickoff"]), h, a)
                if key in have or (div, day, h) in busy or (div, day, a) in busy:
                    continue
                league = LEAGUE_NAMES.get(div) or (women_names() if women else discovered_names()).get(slug, slug)
                fx = {"match_key": key, "division": div, "league": league, "home": h, "away": a,
                      "kickoff_utc": g["kickoff"].isoformat(),
                      "odds": {"home": g["odds"][0], "draw": g["odds"][1], "away": g["odds"][2]},
                      "odds_source": f"{SOURCE} {g['book']}", "p_over25": g["p_over25"]}
                if div in NO_PRIMARY:
                    loc = venue_of(h, division=div, hint=g["venue"])
                    if not loc:
                        skipped.append(f"{h} v {a} ({div}): home ground not found")
                        continue
                    fx.update(venue_lat=loc[0], venue_lon=loc[1], venue_source=loc[2])
                out.append(fx)
                have.add(key)
                busy |= {(div, day, h), (div, day, a)}
                per[div] = per.get(div, 0) + 1
    log(f"espn.com: {len(out)} extra fixture(s)" + (": " + ", ".join(f"{d} {n}" for d, n in sorted(per.items())) if per else ""))
    for s_ in skipped:
        log("  skipped:", s_)
    if bad:
        log(f"  {len(bad)} event(s) unreadable, e.g. {bad[0]}")
    return out
