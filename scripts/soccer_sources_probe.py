"""OddsPapi (free key ODDS_PAPI): rate limits, today's soccer fixtures with odds, one odds payload; KickoffAPI auth and
one fixtures call; whether API_FOOTBALL_KEY is visible. Keys never printed."""
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/json"}
TODAY = date.today()


def get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={**H, **(headers or {})}), timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:800].decode("utf-8", "replace"), dict(e.headers or {})
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}", {}


print("API_FOOTBALL_KEY", "set" if os.environ.get("API_FOOTBALL_KEY") else "NOT SET")
st, b, _ = get("https://docs.oddspapi.io/api-reference/rate-limits.md", {"Accept": "text/markdown"})
print("== OddsPapi rate limits doc", st, re.sub(r"\s+", " ", b)[:2500])
k = os.environ.get("ODDS_PAPI")
if k:
    q = "apiKey=" + urllib.parse.quote(k)
    st, b, hd = get(f"https://api.oddspapi.io/v4/fixtures?sportId=10&from={TODAY}&to={TODAY + timedelta(days=1)}&{q}")
    print("fixtures", st, "| rate headers:", {x: y for x, y in hd.items() if "limit" in x.lower() or "remaining" in x.lower() or "quota" in x.lower()})
    try:
        fx = json.loads(b)
    except ValueError:
        fx = []
        print(b[:500].replace(k, "***"))
    print("fixtures today+tomorrow:", len(fx), "| with odds:", sum(1 for f in fx if f.get("hasOdds")),
          "| statuses:", Counter(f.get("statusName") for f in fx).most_common(5))
    print("keys:", sorted(fx[0].keys()) if fx else None)
    by_t = Counter(f.get("tournamentId") for f in fx if f.get("hasOdds"))
    st2, b2, _ = get(f"https://api.oddspapi.io/v4/tournaments?sportId=10&{q}")
    try:
        tn = {t["tournamentId"]: f"{t['categoryName']}: {t['tournamentName']}" for t in json.loads(b2)}
    except ValueError:
        tn = {}
    print("tournaments with odds:", len(by_t), [(tn.get(t, t), n) for t, n in by_t.most_common(60)])
    young = [tn.get(t, "") for t in by_t if re.search(r"u-?\d{2}|youth|friendl|reserve|women", tn.get(t, ""), re.I)]
    print("youth / friendlies / women with odds:", young[:40])
    one = next((f for f in fx if f.get("hasOdds") and f.get("statusName") in ("Not started", "NotStarted", None) or f.get("hasOdds")), None)
    if one:
        print("sample fixture:", json.dumps({x: one.get(x) for x in ("fixtureId", "tournamentId", "startTime", "participant1Name",
                                                                     "participant2Name", "statusName", "venue", "venueName")}))
        st, b, hd = get(f"https://api.oddspapi.io/v4/odds?fixtureId={one['fixtureId']}&{q}")
        print("odds", st, "| rate headers:", {x: y for x, y in hd.items() if "limit" in x.lower() or "remaining" in x.lower()})
        print(b[:3000].replace(k, "***"))
k2 = os.environ.get("KICKOFF_API")
if k2:
    st, b, _ = get("https://docs.kickoffapi.com/openapi-v2.yaml", {"Accept": "*/*"})
    sec = re.findall(r"securitySchemes:.*?(?=\n\S)", b, re.S)
    print("== KickoffAPI security:", (sec[0][:600] if sec else b[:400]))
    paths = re.findall(r"\n  (/api/v2/[^:\s]+):", b)
    print("paths:", paths[:40])
    for hdr in ({"x-api-key": k2}, {"Authorization": f"Bearer {k2}"}):
        st, b, hd = get(f"https://api.kickoffapi.com/api/v2/fixtures?date={TODAY}", hdr)
        print("fixtures with", list(hdr)[0], st, b[:900].replace(k2, "***"))
        if st == 200:
            break
