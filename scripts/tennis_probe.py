"""Diagnostics: can the Live Tennis API list recently finished Challenger / ITF matches in bulk (for players' last five
matches)? Tries a completed listing, date filters and a player's match list. About 8 of the 100 daily requests.
Prints counts and field names only."""
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




def show(label, d):
    data = (d or {}).get("data") if isinstance(d, dict) else None
    rows = data if isinstance(data, list) else []
    done = [m for m in rows if (m.get("status") or "").lower() == "completed"]
    when = sorted(str(m.get("scheduled_time"))[:10] for m in done)
    print(f"{label}: {len(rows)} rows, {len(done)} completed, dates {when[:1]}..{when[-1:]}, meta {(d or {}).get('meta') if isinstance(d, dict) else None}")
    if done:
        m = done[0]
        print("   keys:", sorted(m.keys()))
        print("   score:", json.dumps(m.get("score"))[:200], "| winner:", m.get("winner"))
    return rows


for tour in ("itf", "challenger"):
    show(f"{tour} completed", get(f"/matches?status=completed&tour={tour}&limit=200"))
show("itf finished", get("/matches?status=finished&tour=itf&limit=200"))
show("itf completed yesterday", get("/matches?status=completed&tour=itf&limit=200&date=2026-11-12"))
show("itf from/to", get("/matches?tour=itf&limit=200&from=2026-11-10&to=2026-11-12"))
up = show("itf upcoming", get("/matches?status=upcoming&tour=itf&limit=5"))
pid = ((up[0].get("players") or {}).get("p1") or {}).get("id") if up else None
if pid:
    show("player matches", get(f"/players/{pid}/matches?limit=20"))
    p = get(f"/players/{pid}")
    print("player keys:", sorted(((p or {}).get("data") or p or {}).keys()) if p else None)
