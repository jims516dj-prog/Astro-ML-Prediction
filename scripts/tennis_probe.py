"""Diagnostics: ITF volume on the Live Tennis API, and whether tournament / fixture look-ups carry results
(so one request could settle a whole event). Uses about 6 of the 100 daily requests. Prints only."""
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


d = get("/matches?status=upcoming&tour=itf&limit=200")
data = (d or {}).get("data") or []
singles = [m for m in data if not m.get("is_doubles")]
print("ITF upcoming page:", len(data), "singles:", len(singles), "meta:", (d or {}).get("meta"))
print("ITF tournaments:", sorted({m.get("tournament") for m in singles})[:40])
print("birthdays known:", sum(1 for m in singles for s in ("p1", "p2") if (m["players"].get(s) or {}).get("birthday")), "of", 2 * len(singles))
tid = singles[0]["tournament_id"] if singles else None
t = get(f"/tournaments/{tid}") if tid else None
print("TOURNAMENT keys:", sorted((t or {}).get("data", t or {}).keys()) if t else None)
print("TOURNAMENT:", json.dumps(t)[:1500] if t else None)
f = get("/fixtures?tour=itf&limit=5")
print("FIXTURES:", json.dumps(f)[:1500] if f else None)
ts = get("/tournaments?tour=challenger&limit=3")
print("TOURNAMENTS list:", json.dumps(ts)[:800] if ts else None)
print("usage:", json.dumps((get("/usage") or {}).get("today")))
