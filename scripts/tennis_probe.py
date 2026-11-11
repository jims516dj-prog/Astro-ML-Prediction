"""Diagnostics: which start times ESPN gives for tennis matches (scheduled vs actual). Prints only."""
import json
import urllib.request
from collections import Counter

HEADERS = {"User-Agent": "astro-football-research (GitHub Actions)"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url} {type(e).__name__}: {e}")
        return None


TIMEY = ("date", "startdate", "enddate", "timevalid", "lastmodified", "wallclock", "clock")


def times(d, path="", out=None, depth=0):
    out = [] if out is None else out
    if depth > 6:
        return out
    if isinstance(d, dict):
        for k, v in d.items():
            p = f"{path}.{k}"
            if any(t in k.lower() for t in TIMEY) and not isinstance(v, (dict, list)):
                out.append((p, v))
            times(v, p, out, depth + 1)
    elif isinstance(d, list):
        for i, v in enumerate(d[:4]):
            times(v, f"{path}[{i}]", out, depth + 1)
    return out


for tour in ("atp", "wta"):
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard")
    if not sb:
        continue
    for e in sb.get("events", [])[:2]:
        comps = [c for g in e.get("groupings", []) if "Singles" in g["grouping"]["displayName"] for c in g["competitions"]]
        print(f"== {tour} {e['name']}: {len(comps)} singles")
        print("  most common start times:", Counter(c.get("date") for c in comps).most_common(5))
        done = [c for c in comps if (c.get("status") or {}).get("type", {}).get("completed")][:2]
        pre = [c for c in comps if (c.get("status") or {}).get("type", {}).get("state") == "pre"][:1]
        for c in done + pre:
            print(" competition", c["id"], c.get("date"), c.get("startDate"), c.get("timeValid"), c["status"]["type"]["name"],
                  [x["athlete"]["displayName"] for x in c["competitors"] if x.get("athlete")])
            core = get(f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/{tour}/events/{e['id']}/competitions/{c['id']}")
            if core:
                print("   core:", times(core)[:20])
                st = (core.get("status") or {}).get("$ref")
                if st:
                    s = get(st.replace("http://", "https://"))
                    print("   core status:", json.dumps(s)[:600] if s else None)
            for ep in ("summary", "playbyplay"):
                d = get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/{ep}?event={c['id']}")
                if d:
                    print(f"   {ep} keys:", sorted(d.keys())[:30], times(d)[:15])
