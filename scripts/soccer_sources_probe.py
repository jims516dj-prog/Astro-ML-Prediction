"""Which soccer API keys are set (names only, never values), and one small test call with each. Prints only."""
import json
import os
import urllib.parse
import urllib.request

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/json"}
CANDIDATES = ["API_FOOTBALL_KEY", "APIFOOTBALL_KEY", "API_SPORTS_KEY", "APISPORTS_KEY", "X_APISPORTS_KEY", "RAPIDAPI_KEY",
              "ODDS_API_IO_KEY", "ODDSAPIIO_KEY", "ODDS_API_IO", "SPORTMONKS_KEY", "SPORTMONKS_TOKEN", "ODDSPAPI_KEY",
              "ODDSLINK_KEY", "THESPORTSDB_KEY", "FIVEDOLLAR_KEY", "FOOTBALL_API_KEY", "SPORTSDATA_KEY", "BSD_KEY",
              "ODDS_API_KEY", "FOOTBALL_DATA_ORG_TOKEN", "LIVETENNISAPI_KEY"]


def get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={**H, **(headers or {})}), timeout=40) as r:
            return r.status, r.read()[:1500].decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:500].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


present = {n: os.environ.get(n) for n in CANDIDATES if os.environ.get(n)}
print("set:", sorted(present), "| not set:", sorted(set(CANDIDATES) - set(present)))
k = next((present[n] for n in ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY", "API_SPORTS_KEY", "APISPORTS_KEY", "X_APISPORTS_KEY") if n in present), None)
if k:
    st, body = get("https://v3.football.api-sports.io/status", {"x-apisports-key": k})
    print("API-Football status:", st, body[:800])
    from datetime import date
    st, body = get(f"https://v3.football.api-sports.io/fixtures?date={date.today().isoformat()}", {"x-apisports-key": k})
    try:
        d = json.loads(body) if st == 200 else {}
    except ValueError:
        d = {}
    print("API-Football fixtures today:", st, "results", d.get("results"), "errors", d.get("errors"), body[:300] if st != 200 else "")
if "RAPIDAPI_KEY" in present:
    st, body = get("https://api-football-v1.p.rapidapi.com/v3/status",
                   {"x-rapidapi-key": present["RAPIDAPI_KEY"], "x-rapidapi-host": "api-football-v1.p.rapidapi.com"})
    print("RapidAPI API-Football status:", st, body[:600])
ko = next((present[n] for n in ("ODDS_API_IO_KEY", "ODDSAPIIO_KEY", "ODDS_API_IO") if n in present), None)
if ko:
    st, body = get("https://api.odds-api.io/v3/leagues?sport=football&apiKey=" + urllib.parse.quote(ko))
    print("Odds-API.io leagues:", st, body[:600])
for n, url, hdr in (("SPORTMONKS_KEY", "https://api.sportmonks.com/v3/core/my/resources", None),
                    ("SPORTMONKS_TOKEN", "https://api.sportmonks.com/v3/core/my/resources", None)):
    if n in present:
        st, body = get(url + "?api_token=" + urllib.parse.quote(present[n]))
        print("Sportmonks:", st, body[:600])
if "THESPORTSDB_KEY" in present:
    st, body = get(f"https://www.thesportsdb.com/api/v1/json/{present['THESPORTSDB_KEY']}/all_leagues.php")
    print("TheSportsDB:", st, body[:300])
