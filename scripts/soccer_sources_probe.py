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


def numeric(d, path=""):
    """Only numbers, booleans and dates from an account answer (never names or e-mail addresses)."""
    out = {}
    if isinstance(d, dict):
        for x, v in d.items():
            out.update(numeric(v, f"{path}{x}."))
    elif isinstance(d, list):
        for i, v in enumerate(d[:3]):
            out.update(numeric(v, f"{path}{i}."))
    elif isinstance(d, (int, float, bool)) or (isinstance(d, str) and d[:2] in ("19", "20") and len(d) <= 30):
        out[path.rstrip(".")] = d
    return out


k = os.environ.get("ODDS_PAPI")
q = "apiKey=" + urllib.parse.quote(k)
st, b = get(f"https://api.oddspapi.io/v4/account?{q}")
try:
    acc = json.loads(b)
    print("oddspapi account:", st, "| fields:", sorted(acc.keys()) if isinstance(acc, dict) else type(acc).__name__)
    print("  ", numeric(acc))
except ValueError:
    print("oddspapi account", st, b[:300].replace(k, "***"))

t = date.today()
fk = os.environ.get("API_FOOTBALL_KEY")
print("API_FOOTBALL_KEY set:", bool(fk))
if fk:
    AF = {"x-apisports-key": fk}
    for path in ("status", f"fixtures?date={t}", f"odds?date={t}", f"fixtures?date={t}&league=10&season={t.year}"):
        st, b = get(f"https://v3.football.api-sports.io/{path}", AF)
        try:
            d = json.loads(b)
        except ValueError:
            print("api-football", path, st, b[:200].replace(fk, "***"))
            continue
        r = d.get("response")
        print(f"api-football {path.split('?')[0]}: HTTP {st} | results {d.get('results')} | errors {d.get('errors')} "
              f"| paging {d.get('paging')}")
        if path == "status" and isinstance(r, dict):
            print("   ", {x: r.get(x) for x in ("subscription", "requests")} if "requests" in r else numeric(r))
        elif isinstance(r, list) and r:
            if path.startswith("fixtures"):
                lg = {}
                for f in r:
                    n = f"{f['league'].get('country')}: {f['league'].get('name')}"
                    lg[n] = lg.get(n, 0) + 1
                print("    leagues:", len(lg), sorted(lg.items(), key=lambda kv: -kv[1])[:40])
                print("    venue sample:", [f["fixture"].get("venue") for f in r[:3]])
            else:
                print("    sample:", json.dumps(r[0])[:600])
raise SystemExit
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
