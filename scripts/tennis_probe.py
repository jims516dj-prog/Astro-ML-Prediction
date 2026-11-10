"""One-off diagnostics for the tennis sources (run on GitHub Actions; prints only, commits nothing)."""
import io
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (astro-football-research)"}


def get(url, n=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            b = r.read()
        print(f"OK {url} {len(b)} bytes")
        return b
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url} {type(e).__name__}: {e}")
        return None


for tour in ("atp", "wta"):
    base = f"https://raw.githubusercontent.com/JeffSackmann/tennis_{tour}/master"
    b = get(f"{base}/{tour}_players.csv")
    if b:
        print(b.decode("latin-1").splitlines()[:3])
    for y in (2023, 2024, 2025, 2026):
        b = get(f"{base}/{tour}_matches_{y}.csv")
        if b:
            lines = b.decode("latin-1").splitlines()
            print(len(lines), lines[0][:400], "| last:", lines[-1][:200])

for path in ("2026/2026.xlsx", "2025/2025.xlsx", "2026w/2026.xlsx", "2025w/2025.xlsx"):
    b = get(f"http://www.tennis-data.co.uk/{path}")
    if b:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(b))
        print(path, df.shape, list(df.columns))
        print(df.tail(2).to_string()[:1500])

for tour in ("atp", "wta"):
    b = get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard")
    if b:
        d = json.loads(b)
        ev = d.get("events", [])
        print(tour, "events", len(ev))
        if ev:
            e = ev[0]
            print(json.dumps({k: e.get(k) for k in ("name", "date", "season")})[:300])
            gs = e.get("groupings") or []
            print("groupings", len(gs))
            for g in gs[:2]:
                comps = g.get("competitions", [])
                print(" grouping", (g.get("grouping") or {}).get("displayName"), len(comps))
                if comps:
                    print(json.dumps(comps[0])[:2500])
