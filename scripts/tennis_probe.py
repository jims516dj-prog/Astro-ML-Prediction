"""One-off diagnostics for the tennis sources (run on GitHub Actions; prints only, commits nothing)."""
import json
import os
import urllib.request

UA = {"User-Agent": "astro-football-research (GitHub Actions)"}


def get(url):
    h = dict(UA)
    if "api.github.com" in url and os.environ.get("GH_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
            b = r.read()
        print(f"OK {url} {len(b)} bytes")
        return b
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {url} {type(e).__name__}: {e}")
        return None


# 1) Sackmann data: repo status and public mirrors
for repo in ("JeffSackmann/tennis_atp", "JeffSackmann/tennis_wta"):
    b = get(f"https://api.github.com/repos/{repo}")
    if b:
        d = json.loads(b)
        print(repo, d.get("full_name"), d.get("default_branch"), d.get("pushed_at"), d.get("size"))
b = get("https://api.github.com/search/repositories?q=tennis_atp+in:name&sort=updated&per_page=15")
if b:
    for it in json.loads(b).get("items", []):
        print(" ", it["full_name"], it["default_branch"], it["pushed_at"], it["size"], it.get("fork"),
              (it.get("license") or {}).get("spdx_id"))

# 2) ESPN history, calendar and athletes
API = "https://site.api.espn.com/apis/site/v2/sports/tennis"
b = get(f"{API}/atp/scoreboard")
if b:
    d = json.loads(b)
    cal = (d.get("leagues") or [{}])[0].get("calendar") or []
    print("calendar entries", len(cal), json.dumps(cal[:3])[:800])
    comp = d["events"][0]["groupings"][0]["competitions"][0]
    print("competition keys", sorted(comp.keys()))
    print("competitor keys", sorted(comp["competitors"][0].keys()))
for tour, day in (("atp", "20250120"), ("wta", "20250120"), ("atp", "20180605"), ("atp", "20100705"), ("atp", "20030616")):
    b = get(f"{API}/{tour}/scoreboard?dates={day}")
    if b:
        d = json.loads(b)
        for e in d.get("events", []):
            singles = [g for g in e.get("groupings", []) if "Singles" in ((g.get("grouping") or {}).get("displayName") or "")]
            n = sum(len(g.get("competitions", [])) for g in singles)
            print(f"  {tour} {day}: {e.get('name')} | {e.get('date')} -> {e.get('endDate')} | singles {n}")
            if singles and singles[0].get("competitions"):
                c = singles[0]["competitions"][0]
                print("   sample", c.get("date"), c.get("round"), json.dumps(c.get("notes"))[:200],
                      [x.get("curatedRank") for x in c["competitors"]], "odds" in c, c.get("venue"))
b = get(f"{API}/atp/scoreboard?dates=20250101-20250131")
if b:
    print("range events", len(json.loads(b).get("events", [])))
for u in ("https://site.web.api.espn.com/apis/common/v3/sports/tennis/athletes/3449",
          "https://sports.core.api.espn.com/v2/sports/tennis/athletes/3449",
          "https://sports.core.api.espn.com/v2/sports/tennis/leagues/atp/athletes/3449"):
    b = get(u)
    if b:
        d = json.loads(b)
        ath = d.get("athlete", d)
        print("  ", {k: ath.get(k) for k in ("displayName", "dateOfBirth", "birthPlace", "hand", "height", "age",
                                         "citizenship", "displayDOB")})
        print("   keys", sorted(ath.keys())[:60])
