"""Diagnostics for tennis odds sources (run on GitHub Actions; prints only, commits nothing)."""
import json
import os
import urllib.request

HEADERS = {"User-Agent": "astro-football-research (GitHub Actions)"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
            b = r.read()
            print(f"OK {url.split('apiKey')[0]} {len(b)} bytes; remaining={r.headers.get('x-requests-remaining')}")
            return json.loads(b)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url.split('apiKey')[0]} {type(e).__name__}: {e}")
        return None


# 1) ESPN: odds on tennis competitions (core API)
sb = get("https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard")
if sb:
    for e in sb.get("events", [])[:2]:
        for g in e.get("groupings", [])[:1]:
            for c in g.get("competitions", [])[:3]:
                eid, cid = e["id"], c["id"]
                for u in (f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/events/{eid}/competitions/{cid}/odds",
                          f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/events/{eid}/competitions/{cid}"):
                    d = get(u)
                    if d:
                        print("   keys", sorted(d.keys())[:40], json.dumps(d)[:600])
# 2) The Odds API: which tennis sports are active (the sports list costs no credits)
key = os.environ.get("ODDS_API_KEY")
if key:
    sports = get(f"https://api.the-odds-api.com/v4/sports?apiKey={key}&all=true") or []
    ten = [s for s in sports if s.get("group") == "Tennis"]
    print("tennis sports:", len(ten), "active:", sum(1 for s in ten if s.get("active")))
    for s in ten:
        print("  ", s["key"], s.get("active"), s.get("title"))
    for s in [s for s in ten if s.get("active")][:6]:
        ev = get(f"https://api.the-odds-api.com/v4/sports/{s['key']}/events?apiKey={key}") or []
        print("   events", s["key"], len(ev), [(e["home_team"], e["away_team"], e["commence_time"]) for e in ev[:3]])
