"""OddsPapi market ids for soccer, and fixtures paging; KickoffAPI fixtures paging and fields. Keys never printed."""
import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/json"}


def get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={**H, **(headers or {})}), timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:600].decode("utf-8", "replace")


k = os.environ.get("ODDS_PAPI")
q = "apiKey=" + urllib.parse.quote(k)
st, b = get(f"https://api.oddspapi.io/v4/markets?sportId=10&{q}")
try:
    ms = json.loads(b)
except ValueError:
    ms = []
    print("markets", st, b[:400].replace(k, "***"))
print("markets:", len(ms), "| keys:", sorted(ms[0].keys()) if ms else None)
for m in ms:
    name = json.dumps(m)
    if any(w in name.lower() for w in ('"1x2', "full time", "match result", "over/under", "totals", "total goals", "both teams")):
        print("  ", name[:420])
t = date.today()
st, b = get(f"https://api.oddspapi.io/v4/fixtures?sportId=10&from={t}&to={t + timedelta(days=2)}&hasOdds=true&{q}")
try:
    fx = json.loads(b)
    print("fixtures 3 days hasOdds=true:", len(fx), "| categories:", sorted({f["categoryName"] for f in fx})[:60])
except ValueError:
    print("fixtures", st, b[:300].replace(k, "***"))
k2 = os.environ.get("KICKOFF_API")
st, b = get(f"https://api.kickoffapi.com/api/v2/fixtures?date={t - timedelta(days=1)}", {"x-api-key": k2})
d = json.loads(b) if st == 200 else {}
print("kickoff yesterday:", st, "| count", len(d.get("data") or []), "| meta", {x: d.get(x) for x in d if x != "data"})
if d.get("data"):
    print("  sample:", json.dumps(d["data"][0])[:700])
