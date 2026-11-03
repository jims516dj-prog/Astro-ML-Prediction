"""Third results source: ESPN's public scoreboard feed (no key needed).

Covers every division we forecast, including the ones football-data.org's free plan does not (lower
English and Scottish tiers, second divisions, Belgium, Greece, Turkey and the extra leagues). Used only
for matches the primary source has not published yet; the primary later confirms or corrects them
(live.settle). Unofficial feed: if it changes or disappears, the cycle just waits for the primary.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta

from .results2 import pair

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
SOURCE = "espn.com"
LEAGUE_SLUG = {
    "E0": "eng.1", "E1": "eng.2", "E2": "eng.3", "E3": "eng.4", "EC": "eng.5",
    "SC0": "sco.1", "SC1": "sco.2", "SC2": "sco.3", "SC3": "sco.4",
    "D1": "ger.1", "D2": "ger.2", "I1": "ita.1", "I2": "ita.2", "SP1": "esp.1", "SP2": "esp.2",
    "F1": "fra.1", "F2": "fra.2", "N1": "ned.1", "B1": "bel.1", "P1": "por.1", "T1": "tur.1", "G1": "gre.1",
    "ARG": "arg.1", "AUT": "aut.1", "BRA": "bra.1", "CHN": "chn.1", "DEN": "den.1", "FIN": "fin.1",
    "IRL": "irl.1", "JAP": "jpn.1", "MEX": "mex.1", "NOR": "nor.1", "POL": "pol.1", "ROM": "rou.1",
    "RUS": "rus.1", "SUI": "sui.1", "SWE": "swe.1", "USA": "usa.1",
}
# Only plain full-time results: a league match decided after extra time or penalties would carry
# 120-minute scores, so it is left for the primary source.
FINAL = {"STATUS_FULL_TIME", "STATUS_FINAL"}


def _get(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (astro-football-research)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("events", [])


def fetch(division: str, date_from: date, date_to: date, base: str = API) -> list[dict]:
    """Raw ESPN events of one division between two dates (inclusive): one range query, or day by day
    if the feed refuses the range."""
    url = f"{base}/{LEAGUE_SLUG[division]}/scoreboard"
    try:
        return _get(f"{url}?dates={date_from:%Y%m%d}-{date_to:%Y%m%d}")
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
    out, d = [], date_from
    while d <= date_to:
        out += _get(f"{url}?dates={d:%Y%m%d}")
        d += timedelta(days=1)
    return out


def normalise(division: str, events: list[dict]) -> list[dict]:
    """ESPN events → the common form used by results2.pair()."""
    out = []
    for e in events:
        status = ((e.get("status") or {}).get("type") or {})
        comp = (e.get("competitions") or [{}])[0]
        if status.get("name") not in FINAL or not status.get("completed"):
            continue
        side = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        if "home" not in side or "away" not in side:
            continue
        try:
            gh, ga = int(side["home"]["score"]), int(side["away"]["score"])
        except (KeyError, TypeError, ValueError):
            continue
        names = lambda c: [(c.get("team") or {}).get(k) or "" for k in            # noqa: E731
                           ("displayName", "shortDisplayName", "name", "abbreviation")]
        out.append({"division": division, "utc": comp.get("date") or e["date"],
                    "home": names(side["home"]), "away": names(side["away"]), "goals_home": gh, "goals_away": ga})
    return out


def match_results(pending: list[dict], fetcher=fetch) -> tuple[dict[str, dict], list[str], dict[str, int]]:
    """Look up every pending forecast's division on ESPN. Returns (found, notes, events-per-division)."""
    by_div: dict[str, list[dict]] = {}
    for r in pending:
        if r["division"] in LEAGUE_SLUG:
            by_div.setdefault(r["division"], []).append(r)
    found, notes, counts = {}, [], {}
    for div, recs in sorted(by_div.items()):
        days = [date.fromisoformat(r["kickoff_utc"][:10]) for r in recs]
        try:
            got = normalise(div, fetcher(div, min(days) - timedelta(days=1), max(days) + timedelta(days=1)))
        except Exception as e:  # noqa: BLE001
            notes.append(f"{div}: unavailable ({type(e).__name__}: {e})")
            continue
        counts[div] = len(got)
        f, n = pair(recs, got, SOURCE)
        found.update(f)
        notes += n
    return found, notes, counts
