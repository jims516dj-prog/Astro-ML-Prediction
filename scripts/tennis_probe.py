"""Diagnostics for the Live Tennis API key (free tier): checks the key, the quota, and the shape of an upcoming
Challenger match. Uses 2-3 of the 100 daily requests. Prints only."""
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


if not KEY:
    print("LIVETENNISAPI_KEY is not set (add it as a GitHub secret)")
else:
    print("usage:", json.dumps(get("/usage"))[:400])
    d = get("/matches?status=upcoming&tour=challenger&limit=3")
    if d:
        print("meta:", d.get("meta"))
        for m in (d.get("data") or [])[:2]:
            print(json.dumps(m)[:1500])
    d = get("/matches?status=upcoming&tour=atp&limit=200")
    if d:
        names = sorted({m.get("tournament") for m in d.get("data") or []})
        print("ATP tournaments listed:", names[:40])
