"""Test calls with API_FOOTBALL_KEY, ODDS_PAPI and KICKOFF_API (keys never printed) and their documentation."""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date

H = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/json"}
TODAY = date.today().isoformat()


def get(url, headers=None, n=2500):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={**H, **(headers or {})}), timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")[:n * 20]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:800].decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def hide(s, k):
    return s.replace(k, "***") if k else s


for n in ("API_FOOTBALL_KEY", "ODDS_PAPI", "KICKOFF_API"):
    print(n, "set" if os.environ.get(n) else "NOT SET")

k = os.environ.get("API_FOOTBALL_KEY")
if k:
    hd = {"x-apisports-key": k}
    print("\n== API-Football")
    st, b = get("https://v3.football.api-sports.io/status", hd); print("status", st, hide(b[:600], k))
    st, b = get(f"https://v3.football.api-sports.io/fixtures?date={TODAY}", hd)
    try:
        d = json.loads(b)
        fx = d.get("response") or []
        print("fixtures today:", st, "results", d.get("results"), "errors", d.get("errors"))
        lg = {}
        for f in fx:
            lg[f["league"]["name"] + " (" + f["league"]["country"] + ")"] = lg.get(f["league"]["name"] + " (" + f["league"]["country"] + ")", 0) + 1
        print("leagues today:", len(lg), sorted(lg.items(), key=lambda x: -x[1])[:25])
        youth = [n for n in lg if re.search(r"U-?\d{2}|youth|friendl", n, re.I)]
        print("youth / friendlies:", youth[:25])
        if fx:
            f = fx[0]
            print("sample:", json.dumps({"fixture": {k2: f["fixture"].get(k2) for k2 in ("id", "date", "venue", "status")},
                                         "league": f["league"], "teams": f["teams"]})[:900])
    except ValueError:
        print("fixtures:", st, hide(b[:400], k))
    st, b = get(f"https://v3.football.api-sports.io/odds?date={TODAY}&page=1", hd)
    try:
        d = json.loads(b)
        print("odds today page 1:", st, "results", d.get("results"), "paging", d.get("paging"), "errors", d.get("errors"))
        if d.get("response"):
            o = d["response"][0]
            bk = o.get("bookmakers") or []
            print("odds sample league", o["league"]["name"], "| bookmakers", len(bk), [b2["name"] for b2 in bk][:6],
                  "| markets of first:", [m["name"] for m in (bk[0]["bets"] if bk else [])][:8])
    except ValueError:
        print("odds:", st, hide(b[:400], k))

k = os.environ.get("ODDS_PAPI")
print("\n== OddsPapi docs")
for u in ("https://oddspapi.io/llms.txt", "https://docs.oddspapi.io/llms.txt", "https://oddspapi.io/blog/?p=3128"):
    st, b = get(u, {"Accept": "text/markdown,text/plain,*/*"})
    txt = re.sub(r"<[^>]+>", " ", b)
    txt = re.sub(r"\s+", " ", txt)
    hits = re.findall(r"[^.]*(?:api\.oddspapi|apiKey|api_key|/v\d/|free|requests|limit)[^.]*\.", txt, re.I)
    print(" ", u, st, " | ".join(hits[:14])[:2500])
if k:
    print("== OddsPapi calls")
    for path in ("/v4/sports", "/v4/bookmakers", "/v4/tournaments?sportId=10", "/v4/fixtures?sportId=10&from=" + TODAY + "&to=" + TODAY):
        for base in ("https://api.oddspapi.io",):
            st, b = get(base + path + ("&" if "?" in path else "?") + "apiKey=" + urllib.parse.quote(k))
            print(" ", path, st, hide(b[:700], k))

k = os.environ.get("KICKOFF_API")
print("\n== KickoffAPI docs")
for u in ("https://sportsapis.dev/apis/kickoffapi", "https://kickoffapi.com/llms.txt", "https://kickoffapi.com", "https://docs.kickoffapi.com"):
    st, b = get(u, {"Accept": "text/markdown,text/plain,*/*"})
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))
    hits = re.findall(r"[^.]*(?:https?://[a-z0-9.-]*kickoff[a-z0-9./-]*|api[_-]?key|header|free|requests|odds|venue|endpoint)[^.]*\.", txt, re.I)
    urls = sorted(set(re.findall(r"https?://[a-z0-9.-]*kickoff[a-z0-9./_-]*", b, re.I)))
    print(" ", u, st, "| urls:", urls[:15], "|", " | ".join(hits[:12])[:2000])
