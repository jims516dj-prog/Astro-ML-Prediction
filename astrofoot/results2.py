"""Second results source: football-data.org (official API, free plan, personal key).

Used only to settle forecasts that football-data.co.uk (the primary source) has not published yet,
usually minutes after full time instead of days. Every result records its source; when the primary
source later publishes the same match, live.settle() compares them and appends a correction if they
disagree.

The free plan covers these of our divisions: Premier League (E0), Championship (E1), Bundesliga (D1),
Serie A (I1), La Liga (SP1), Ligue 1 (F1), Eredivisie (N1), Primeira Liga (P1), Brasileirão (BRA), and the
UEFA Champions League (UCL).
"""
from __future__ import annotations

import difflib
import json
import os
import unicodedata
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

API = "https://api.football-data.org/v4"
SOURCE = "football-data.org"
COMPETITION_DIV = {"PL": "E0", "ELC": "E1", "BL1": "D1", "SA": "I1", "PD": "SP1", "FL1": "F1", "DED": "N1",
                   "PPL": "P1", "BSA": "BRA", "CL": "UCL"}
MAX_SPAN_DAYS = 10            # the API's dateFrom..dateTo limit

_DROP = {"fc", "cf", "afc", "sc", "ac", "as", "ss", "ssc", "sl", "sv", "vfb", "vfl", "tsg", "rcd", "rc", "ud", "sd",
         "cd", "ca", "cr", "us", "club", "de", "del", "la", "le", "the", "futbol", "football", "calcio", "1",
         "sad", "clube", "fk", "bk", "if", "ec", "se", "esporte"}
_EXPAND = {"man": "manchester", "utd": "united", "nottm": "nottingham", "sp": "sporting", "ath": "atletico",
           "st": "saint", "wolves": "wolverhampton", "spurs": "tottenham", "psg": "paris saint germain",
           "inter": "internazionale", "sociedad": "real sociedad", "betis": "real betis", "qpr": "queens park rangers"}


def token() -> str | None:
    return os.environ.get("FOOTBALL_DATA_ORG_TOKEN") or None


def _tokens(name: str) -> set[str]:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace(".", ""))
    out = set()
    for t in s.split():
        t = _EXPAND.get(t, t)
        out |= {x for x in t.split() if x not in _DROP}
    return out


def similarity(a: str, b: str) -> float:
    """0..1 similarity of two team names written by different sources."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    if ta <= tb or tb <= ta:
        return 0.9
    jac = len(ta & tb) / len(ta | tb)
    seq = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(jac, seq * 0.85)


def fetch(date_from: date, date_to: date, tok: str, base: str = API) -> list[dict]:
    """Finished matches between two dates (inclusive), in windows the API accepts."""
    out, d = [], date_from
    while d <= date_to:
        end = min(date_to, d + timedelta(days=MAX_SPAN_DAYS - 1))
        q = urllib.parse.urlencode({"dateFrom": d.isoformat(), "dateTo": end.isoformat(), "status": "FINISHED"})
        req = urllib.request.Request(f"{base}/matches?{q}", headers={"X-Auth-Token": tok,
                                                                      "User-Agent": "astro-football-research"})
        with urllib.request.urlopen(req, timeout=30) as r:
            out += json.loads(r.read()).get("matches", [])
        d = end + timedelta(days=1)
    return out


def normalise(matches: list[dict]) -> list[dict]:
    """football-data.org matches → the common form used by pair()."""
    out = []
    for m in matches:
        div = COMPETITION_DIV.get((m.get("competition") or {}).get("code"))
        sc = m.get("score") or {}
        ft = sc.get("regularTime") or sc.get("fullTime") or {}      # 90 minutes, like the primary source
        if div and m.get("status") == "FINISHED" and ft.get("home") is not None and ft.get("away") is not None:
            out.append({"division": div, "utc": m["utcDate"],
                        "home": [m["homeTeam"].get(k) or "" for k in ("name", "shortName", "tla")],
                        "away": [m["awayTeam"].get(k) or "" for k in ("name", "shortName", "tla")],
                        "goals_home": int(ft["home"]), "goals_away": int(ft["away"])})
    return out


def pair(pending: list[dict], matches: list[dict], source: str) -> tuple[dict[str, dict], list[str]]:
    """Pair our pending forecasts with another source's finished matches (common form).

    Same division and kickoff within 3 h, then team-name similarity. With a single candidate in that
    slot a modest similarity suffices; with several, the best must clearly beat the runner-up.
    Uncertain pairs are left unresolved (and listed), never guessed.
    Returns ({match_key: {goals_home, goals_away, source}}, notes).
    """
    by_div: dict[str, list[dict]] = {}
    for m in matches:
        by_div.setdefault(m["division"], []).append(m)
    sim = lambda name, names: max(similarity(name, n) for n in names)      # noqa: E731
    found, notes = {}, []
    for rec in pending:
        ko = datetime.fromisoformat(rec["kickoff_utc"])
        cands = [m for m in by_div.get(rec["division"], [])
                 if abs((datetime.fromisoformat(m["utc"].replace("Z", "+00:00")) - ko).total_seconds()) <= 3 * 3600]
        if not cands:
            continue
        scored = sorted(((sim(rec["home"], m["home"]), sim(rec["away"], m["away"]), m) for m in cands),
                        key=lambda x: -(x[0] + x[1]))
        sh, sa, m = scored[0]
        if len(scored) == 1:
            ok = max(sh, sa) >= 0.5 and min(sh, sa) >= 0.2
        else:
            ok = min(sh, sa) >= 0.35 and (sh + sa) - (scored[1][0] + scored[1][1]) >= 0.3
        if ok:
            found[rec["match_key"]] = {"goals_home": m["goals_home"], "goals_away": m["goals_away"], "source": source}
        else:
            notes.append(f"{rec['home']} v {rec['away']}: no confident match among "
                         + "; ".join(f"{c['home'][0]} v {c['away'][0]}" for c in cands))
    return found, notes


def match_results(pending: list[dict], matches: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """Pair pending forecasts with football-data.org's raw matches."""
    return pair(pending, normalise(matches), SOURCE)
