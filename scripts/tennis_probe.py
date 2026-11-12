"""Diagnostics for the Live Tennis API key: one full upcoming Challenger singles match and one finished one.
Uses 2-3 of the 100 daily requests. Prints only."""
import json
import os
import urllib.request

KEY = os.environ.get("LIVETENNISAPI_KEY")
BASE = "https://api.livetennisapi.com/api/public/v1"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json",
                                                       "User-Agent": "astro-football-research"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {path}: {type(e).__name__}: {e}")
        return None


d = get("/matches?status=upcoming&tour=challenger&limit=200")
data = (d or {}).get("data") or []
singles = [m for m in data if not m.get("is_doubles")]
print("upcoming challenger:", len(data), "singles:", len(singles), "meta:", (d or {}).get("meta"))
print("tournaments:", sorted({m.get("tournament") for m in singles}))
print("top-level tour values:", sorted({str(m.get("tour")) for m in data}), "gender:", sorted({str(m.get("gender")) for m in data}))
if singles:
    m = singles[0]
    print("KEYS:", sorted(m.keys()))
    print(json.dumps({k: v for k, v in m.items() if k != "players"})[:1500])
    print("P1:", json.dumps(m["players"]["p1"])[:800])
# a finished match: look up an older id near the first upcoming one
if singles:
    for back in (400, 800, 1500):
        x = get(f"/matches/{int(singles[0]['id']) - back}")
        if x:
            x = x.get("data", x)
            print("LOOKUP", back, json.dumps({k: x.get(k) for k in ("id", "status", "event_status", "outcome", "winner", "score",
                                                                     "tournament", "tour", "is_doubles", "format")})[:900])
            if (x.get("status") or "") == "completed" and not x.get("is_doubles"):
                break
