"""Diagnostics: Odds-API.io documentation (free tier, endpoints). Prints only."""
import urllib.request

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "text/markdown"}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return f"FAIL {url}: {type(e).__name__}: {e}"


idx = get("https://docs.odds-api.io/llms.txt")
print(idx[:4000])
for path in ("/index.md", "/quickstart.md", "/pricing.md", "/rate-limits.md", "/api-reference/events/get-events.md",
             "/api-reference/odds/get-odds.md", "/api-reference/leagues/get-leagues.md"):
    t = get("https://docs.odds-api.io" + path)
    print("\n=====", path, "\n", t[:2500])
