"""Diagnostics: free sources of Challenger / Hopman Cup results (prints only, commits nothing)."""
import json
import os
import urllib.request

HEADERS = {"User-Agent": "astro-football-research (GitHub Actions)", "Accept": "application/vnd.github+json"}


def get(url, raw=False):
    h = dict(HEADERS)
    if "api.github.com" in url and os.environ.get("GH_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
            b = r.read()
            return b if raw else json.loads(b)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url} {type(e).__name__}: {e}")
        return None


for q in ("atp_matches_qual_chall_2025", "atp_matches_qual_chall_2026", "challenger tennis results csv 2026",
          "tennis_atp fork", "atp challenger matches dataset"):
    d = get("https://api.github.com/search/repositories?per_page=10&sort=updated&q=" + urllib.parse.quote(q)) if False else None
import urllib.parse  # noqa: E402
for q in ("tennis_atp", "tennis atp challenger", "atp challenger", "tennis_wta", "hopman cup"):
    d = get("https://api.github.com/search/repositories?per_page=12&sort=updated&q=" + urllib.parse.quote(q))
    print(f"== repos '{q}'")
    for it in (d or {}).get("items", []):
        print("  ", it["full_name"], "| pushed", it["pushed_at"][:10], "| size", it["size"], "| fork", it["fork"],
              "| licence", (it.get("license") or {}).get("spdx_id"), "|", (it.get("description") or "")[:90])
# code search for the Sackmann Challenger file names (shows which repos still carry them, and how recent)
for name in ("atp_matches_qual_chall_2025.csv", "atp_matches_qual_chall_2026.csv", "wta_matches_qual_itf_2025.csv"):
    d = get("https://api.github.com/search/code?per_page=15&q=" + urllib.parse.quote(f"filename:{name}"))
    print(f"== files named {name}: {(d or {}).get('total_count')}")
    for it in (d or {}).get("items", []):
        print("  ", it["repository"]["full_name"], it["path"])
