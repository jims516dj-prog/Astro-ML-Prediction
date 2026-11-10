"""Diagnostics: which tennis competitions ESPN lists beyond the ATP and WTA tours (prints only)."""
import json
import urllib.request

HEADERS = {"User-Agent": "astro-football-research (GitHub Actions)"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url} {type(e).__name__}: {e}")
        return None


d = get("https://sports.core.api.espn.com/v2/sports/tennis/leagues?limit=100")
if d:
    print("leagues:", d.get("count"))
    for it in d.get("items", []):
        lg = get(it["$ref"].replace("http://", "https://"))
        if lg:
            print(" ", lg.get("slug"), "|", lg.get("name"), "|", lg.get("abbreviation"))
for slug in ("atp", "wta", "atp-challenger", "challenger", "itf", "itf-men", "itf-women", "davis-cup", "billie-jean-king-cup",
             "united-cup", "laver-cup", "olympics", "exhibition"):
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/tennis/{slug}/scoreboard")
    if sb:
        ev = sb.get("events", [])
        n = sum(len(g.get("competitions", [])) for e in ev for g in e.get("groupings", []))
        print(f"scoreboard {slug}: {len(ev)} events, {n} competitions:", [e.get("name") for e in ev][:6])
