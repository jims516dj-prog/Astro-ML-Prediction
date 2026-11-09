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
import urllib.request
from datetime import datetime, timedelta

from .dataset import LEAGUE_NAMES, MULTI_CLUB, NO_PRIMARY
from .fixtures2 import canonical_name, european_name
from .results_espn import LEAGUE_SLUG

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
SOURCE = "espn.com"
DAYS_AHEAD = 2                 # today and tomorrow (the cycle runs three times a day)


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
                   log=print) -> list[dict]:
    """Fixtures (with odds) ESPN lists that `primary` does not, in the form of live.parse_fixtures.
    known_of(div) -> football-data.co.uk names for one of our leagues; multi_pool: names for cups/European ties."""
    busy = {(f["division"], f["kickoff_utc"][:10], t) for f in primary for t in (f["home"], f["away"])}
    have = {f["match_key"] for f in primary} | {r["match_key"] for r in ledger_preds}
    out, skipped, per, bad = [], [], {}, []
    for div, slug in sorted(LEAGUE_SLUG.items()):
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
                fx = {"match_key": key, "division": div, "league": LEAGUE_NAMES.get(div, div), "home": h, "away": a,
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
