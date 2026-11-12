"""Diagnostics: free soccer sources for games, venues and odds the app does not cover yet. Prints only."""
import json
import urllib.request
from datetime import date

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/json"}


def get(url, raw=False):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=40) as r:
            b = r.read()
            return b[:3000].decode("utf-8", "replace") if raw else json.loads(b)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url}: {type(e).__name__}: {e}")
        return None


today = date.today().isoformat()
print("== Odds-API.io (no key)")
for u in ("https://api.odds-api.io/v3/sports", "https://api.odds-api.io/v3/bookmakers",
          "https://api.odds-api.io/v3/leagues?sport=football", "https://docs.odds-api.io/"):
    d = get(u, raw=True)
    print(" ", u, "->", (d or "")[:700].replace("\n", " "))
print("== TheSportsDB (free test key 123)")
d = get(f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={today}&s=Soccer")
ev = (d or {}).get("events") or []
print("  events today:", len(ev))
for e in ev[:6]:
    print("   ", e.get("strLeague"), "|", e.get("strEvent"), "|", e.get("strTimestamp"), "| venue:", e.get("strVenue"), e.get("strCountry"))
leagues = sorted({e.get("strLeague") for e in ev})
print("  leagues:", len(leagues), leagues[:40])
d = get("https://www.thesportsdb.com/api/v1/json/123/searchteams.php?t=Grenada")
print("  team search Grenada:", [(t.get("strTeam"), t.get("strStadium"), t.get("strLocation")) for t in (d or {}).get("teams") or []][:3])
print("== OpenLigaDB (German leagues)")
d = get("https://api.openligadb.de/getmatchdata/bl3")
print("  3. Liga current matchday:", len(d or []), [(m.get("team1", {}).get("teamName"), m.get("team2", {}).get("teamName"), m.get("matchDateTimeUTC")) for m in (d or [])[:3]])
d = get("https://api.openligadb.de/getavailableleagues")
print("  leagues:", len(d or []), sorted({x.get("leagueShortcut") for x in (d or [])})[:60])
