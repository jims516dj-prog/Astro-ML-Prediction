"""Diagnostics: are the FIFA U17 World Cup, the UEFA Youth League and the women's U19 Euro in the sources, and priced?

ESPN: which youth competitions its league list has, and their games (today to +3 days) with or without odds.
API-Football: the leagues its search finds for these names, their games yesterday to tomorrow, and whether one game
of each has odds. About 12 of the 100 daily API-Football requests. Prints names, counts and dates only."""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrofoot import fixtures_apifootball as af  # noqa: E402
from astrofoot import fixtures_espn as fe  # noqa: E402

now = datetime.now(timezone.utc)
WANT = re.compile(r"u-?17|u-?19|youth|junior|under.?1[79]", re.I)

print("== ESPN")
try:
    import json
    import urllib.request
    raw = urllib.request.urlopen(urllib.request.Request(fe.CORE, headers={"User-Agent": "astro-football-research"}),
                                 timeout=30).read()
    refs = [i.get("$ref", "") for i in json.loads(raw).get("items", [])]
    slugs = sorted({m.group(1) for r in refs for m in [re.search(r"/leagues/([^/?]+)", r)] if m})
    youth = [s for s in slugs if WANT.search(s)]
    print(f"{len(slugs)} competitions; youth-like slugs: {youth}")
    for s in youth:
        n = priced = 0
        names = set()
        for k in range(4):
            for e in fe.fetch(s, now + timedelta(days=k)):
                n += 1
                names.add(((e.get("season") or {}).get("slug")) or "")
                priced += any(c.get("odds") for c in e.get("competitions", []))
        print(f"  {s}: {n} games in the next 4 days, {priced} with odds")
except Exception as e:  # noqa: BLE001
    print("ESPN unavailable:", type(e).__name__, e)

print("== API-Football")
c = af.client()
if not c:
    print("no API_FOOTBALL_KEY")
    raise SystemExit
for q in ("U17", "Youth League", "U19"):
    try:
        res = c.get("leagues", search=q).get("response") or []
    except Exception as e:  # noqa: BLE001
        print(f"search {q!r}: {type(e).__name__}: {e}")
        continue
    hits = [(x["league"]["id"], f"{(x.get('country') or {}).get('name')}: {x['league']['name']}",
             [s["year"] for s in x.get("seasons") or [] if s.get("current")]) for x in res]
    keep = [h for h in hits if re.search(r"world cup|youth league|euro|championship", h[1], re.I)]
    print(f"search {q!r}: {len(hits)} leagues; relevant: {keep[:12]}")
days = [(now + timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1)]
for d in days:
    try:
        fx = c.get("fixtures", date=d).get("response") or []
    except Exception as e:  # noqa: BLE001
        print(d, type(e).__name__, e)
        continue
    sel = [f for f in fx if re.search(r"u-?17 world cup|world cup - u17|youth league|u19.*women|women.*u19",
                                      f"{f['league'].get('country')}: {f['league']['name']}", re.I)]
    leagues = {}
    for f in sel:
        leagues.setdefault(f"{f['league']['id']} {f['league'].get('country')}: {f['league']['name']}", []).append(f)
    print(f"{d}: {len(fx)} games in all; of these competitions: {[(k, len(v)) for k, v in leagues.items()]}")
    for k, v in leagues.items():
        f = v[0]
        try:
            o = c.get("odds", fixture=f["fixture"]["id"]).get("response") or []
            bks = len((o[0].get("bookmakers") or [])) if o else 0
        except Exception as e:  # noqa: BLE001
            bks = f"{type(e).__name__}"
        print(f"   {k}: e.g. {f['teams']['home']['name']} v {f['teams']['away']['name']} -> bookmakers with odds: {bks}")
print("requests left today:", c.left())
