"""Build data/ref/team_foundings.csv from Wikidata (CC0): founding dates of football clubs,
national teams and the nations they represent.

  python scripts/fetch_foundings.py            # needs access to query.wikidata.org and www.wikidata.org

Two stages, because the SPARQL service cuts queries off at 60 s:
  1. SPARQL, kept minimal: item ids + inception (P571) and its precision, in 10-year chunks
  2. the Wikidata API (wbgetentities, 50 items per request) for labels, aliases, country and places

One row per (team, chart kind):
  club           inception of an association football club (Q476028)
  national_team  inception of a national association football team (Q6979593)
  nation         inception of the country it represents (P1532): Rao's "nation chart"
Founding place: location of formation (P740), else headquarters (P159), else home venue (P115),
else the administrative area (P131): the first that has coordinates. For nations: the capital (P36).
Founding times are essentially never recorded; `founded_time` is left blank for the user to add.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ref" / "team_foundings.csv"
SPARQL = "https://query.wikidata.org/sparql"
API = "https://www.wikidata.org/w/api.php"
UA = "astro-football-research/1.0 (https://github.com/jims516dj-prog/Astro-ML-Prediction)"
PRECISION = {9: "year", 10: "month", 11: "day"}
PLACE_PROPS = ("P740", "P159", "P115", "P131")
FIELDS = ["team", "kind", "founded_date", "date_precision", "founded_time", "place", "lat", "lon",
          "country", "aliases", "sitelinks", "source", "date_source"]
WIKI = "https://en.wikipedia.org/w/api.php"
ENRICH_TOP = 8000          # clubs (by sitelinks) whose year/month-only date we try to refine from Wikipedia
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], 1)}

# Wikidata files clubs under several classes (verified with --probe): "association football club"
# (Q476028; Man United, AC Milan), "men's association football team" (Q103229495; Chelsea, FC Barcelona)
# and plain "sports club" (Q847017; Boca Juniors), the last only when its sport (P641) is association
# football (Q2736). Any statement rank counts (p:P31), so a different *preferred* class does not hide a club.
# Deprecated inception statements are skipped.
CLUBS = """SELECT DISTINCT ?item ?inc ?pr WHERE {
  { VALUES ?cls { wd:Q476028 wd:Q103229495 } ?item p:P31/ps:P31 ?cls . }
  UNION { ?item p:P31/ps:P31 wd:Q847017 ; wdt:P641 wd:Q2736 . }
  ?item p:P571 ?st .
  ?st psv:P571 ?tv ; wikibase:rank ?rk . FILTER(?rk != wikibase:DeprecatedRank)
  ?tv wikibase:timeValue ?inc ; wikibase:timePrecision ?pr .
  FILTER(?inc >= "%d-01-01T00:00:00Z"^^xsd:dateTime && ?inc < "%d-01-01T00:00:00Z"^^xsd:dateTime)
}"""
NATIONAL = """SELECT ?item ?inc ?pr ?nation ?ninc ?npr WHERE {
  ?item wdt:P31 wd:Q6979593 .
  OPTIONAL { ?item p:P571/psv:P571 ?tv . ?tv wikibase:timeValue ?inc ; wikibase:timePrecision ?pr . }
  OPTIONAL { ?item wdt:P1532 ?nation .
             OPTIONAL { ?nation p:P571/psv:P571 ?ntv . ?ntv wikibase:timeValue ?ninc ; wikibase:timePrecision ?npr . } }
}"""


def _get(url: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _retry(fn, what: str, tries: int = 5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - both services throttle and time out under load
            print(f"  {what}: attempt {i + 1} failed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            time.sleep(5 * 2 ** i)
    raise SystemExit(f"{what}: failed repeatedly")


def sparql(q: str) -> list[dict]:
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    rows = _retry(lambda: _get(url), "sparql")["results"]["bindings"]
    return [{k: v["value"] for k, v in r.items()} for r in rows]


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri else ""


def entities(ids: set[str], props: str = "labels|aliases|claims|sitelinks") -> dict[str, dict]:
    out, ids = {}, sorted(i for i in ids if i)
    for k in range(0, len(ids), 50):
        batch = ids[k:k + 50]
        url = API + "?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(batch),
                                                  "props": props, "languages": "en", "format": "json"})
        out.update(_retry(lambda: _get(url), f"entities {k}/{len(ids)}").get("entities", {}))
        if k and k % 2500 == 0:
            print(f"  entities {k}/{len(ids)}", flush=True)
        time.sleep(0.2)
    return out


def sitelinks(e: dict) -> int:
    return len(e.get("sitelinks", {}))


def enwiki(e: dict) -> str:
    return (e.get("sitelinks", {}).get("enwiki") or {}).get("title", "")


def label(e: dict | None) -> str:
    return ((e or {}).get("labels", {}).get("en") or {}).get("value", "")


def aliases(e: dict) -> str:
    return "|".join(a["value"] for a in e.get("aliases", {}).get("en", []))


def claim_ids(e: dict, prop: str) -> list[str]:
    out = []
    for c in e.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def coord(e: dict | None):
    for c in (e or {}).get("claims", {}).get("P625", []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "latitude" in v:
            return f"{v['latitude']:.5f}", f"{v['longitude']:.5f}"
    return "", ""


def date_of(inc: str, pr: str) -> tuple[str, str]:
    p = PRECISION.get(int(pr) if pr else 0, "")
    d = inc.lstrip("+")[:10] if inc else ""
    return d, p


def build_rows(clubs: list[dict], national: list[dict], fetch=entities) -> list[dict]:
    """Pure function of the SPARQL rows + an entity fetcher (injectable for tests)."""
    team_ids = {qid(r["item"]) for r in clubs + national}
    nation_ids = {qid(r.get("nation", "")) for r in national} - {""}
    ents = fetch(team_ids | nation_ids)
    places = {p for i in team_ids for prop in PLACE_PROPS for p in claim_ids(ents.get(i, {}), prop)}
    capitals = {c for n in nation_ids for c in claim_ids(ents.get(n, {}), "P36")}
    countries = {c for i in team_ids for c in claim_ids(ents.get(i, {}), "P17")}
    ents.update(fetch((places | capitals | countries) - set(ents), "labels|claims"))

    def place_of(e):
        for prop in PLACE_PROPS:
            for p in claim_ids(e, prop):
                lat, lon = coord(ents.get(p))
                if lat:
                    return label(ents.get(p)), lat, lon
        return "", "", ""

    rows, seen = [], set()
    nations: dict[str, dict] = {}
    for r, kind in [(r, "club") for r in clubs] + [(r, "national_team") for r in national]:
        i = qid(r["item"])
        e = ents.get(i, {})
        d, p = date_of(r.get("inc", ""), r.get("pr", ""))
        country = ", ".join(label(ents.get(c)) for c in claim_ids(e, "P17")[:1])
        if kind == "national_team":
            country = label(ents.get(qid(r.get("nation", "")))) or country
        if d and p and (i, kind) not in seen:
            seen.add((i, kind))
            pl, lat, lon = place_of(e)
            rows.append(dict(zip(FIELDS, [label(e) or i, kind, d, p, "", pl, lat, lon, country, aliases(e),
                                          sitelinks(e), f"wikidata:{i}", "wikidata"])))
            rows[-1]["_enwiki"] = enwiki(e)
        n = qid(r.get("nation", ""))
        nd, npr = date_of(r.get("ninc", ""), r.get("npr", ""))
        if kind == "national_team" and n and nd and npr:
            # one "nation" chart per country, findable by the country's name and by its teams' names
            rec = nations.setdefault(n, {"date": (nd, npr), "names": set()})
            rec["names"] |= {label(e), *[a for a in aliases(e).split("|") if a]}
    for n, rec in nations.items():
        en = ents.get(n, {})
        cap = next(iter(claim_ids(en, "P36")), "")
        lat, lon = coord(ents.get(cap))
        name = label(en) or n
        als = "|".join(sorted(x for x in rec["names"] if x and x != name))
        rows.append(dict(zip(FIELDS, [name, "nation", rec["date"][0], rec["date"][1], "", label(ents.get(cap)),
                                      lat, lon, name, als, sitelinks(en), f"wikidata:{n}", "wikidata"])))
    rows.sort(key=lambda r: (r["team"].lower(), r["kind"]))
    return rows


def infobox_founded(wikitext: str) -> tuple[int, int, int] | None:
    """Exact founding date from an infobox `founded =` field: {{Start date|Y|M|D}} or 'D Month YYYY' / 'Month D, YYYY'."""
    import re
    m = re.search(r"^\s*\|\s*(?:founded|formation|established)\s*=(.*)$", wikitext, re.I | re.M)
    if not m:
        return None
    v = m.group(1)
    t = re.search(r"\{\{\s*(?:start date and age|start date|founded date)\s*\|([^}]*)\}\}", v, re.I)
    if t:   # positional numbers only: {{Start date and age|df=yes|1887|11|6}} -> 1887, 11, 6
        nums = [x.strip() for x in t.group(1).split("|") if "=" not in x and x.strip().isdigit()]
        if len(nums) >= 3:
            return int(nums[0]), int(nums[1]), int(nums[2])
    t = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", v)
    if t and t.group(2).lower() in MONTHS:
        return int(t.group(3)), MONTHS[t.group(2).lower()], int(t.group(1))
    t = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", v)
    if t and t.group(1).lower() in MONTHS:
        return int(t.group(3)), MONTHS[t.group(1).lower()], int(t.group(2))
    return None


def enrich_from_wikipedia(rows: list[dict], top: int = ENRICH_TOP) -> int:
    """Refine year/month-only club dates from English Wikipedia infoboxes; keep only if the year agrees."""
    cand = sorted((r for r in rows if r["kind"] == "club" and r["date_precision"] != "day" and r.get("_enwiki")),
                  key=lambda r: -int(r["sitelinks"]))[:top]
    by_title = {r["_enwiki"]: r for r in cand}
    titles, fixed = list(by_title), 0
    for k in range(0, len(titles), 50):
        batch = titles[k:k + 50]
        url = WIKI + "?" + urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content",
                                                   "rvslots": "main", "titles": "|".join(batch),
                                                   "redirects": 1, "format": "json", "formatversion": 2})
        pages = _retry(lambda: _get(url), f"wikipedia {k}/{len(titles)}").get("query", {})
        redirect = {r["to"]: r["from"] for r in pages.get("redirects", [])}
        for pg in pages.get("pages", []):
            revs = pg.get("revisions") or []
            if not revs:
                continue
            r = by_title.get(redirect.get(pg["title"], pg["title"]))
            got = infobox_founded(revs[0]["slots"]["main"]["content"])
            if r and got and str(got[0]) == r["founded_date"][:4] and 1 <= got[1] <= 12 and 1 <= got[2] <= 31:
                r["founded_date"] = f"{got[0]:04d}-{got[1]:02d}-{got[2]:02d}"
                r["date_precision"] = "day"
                r["date_source"] = f"en.wikipedia infobox ({pg['title']})"
                fixed += 1
        time.sleep(0.5)
    return fixed


def main():
    clubs = []
    for lo in range(1800, 2030, 10):
        part = sparql(CLUBS % (lo, lo + 10))
        print(f"clubs founded {lo}s: {len(part)}", flush=True)
        clubs += part
        time.sleep(1)
    national = sparql(NATIONAL)
    print(f"national teams: {len(national)}; fetching names, aliases and places ...", flush=True)
    rows = build_rows(clubs, national)
    print(f"refining year-only dates of the {ENRICH_TOP} most prominent clubs from Wikipedia ...", flush=True)
    print(f"  exact dates recovered: {enrich_from_wikipedia(rows)}", flush=True)
    for r in rows:
        r.pop("_enwiki", None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    kinds = {k: sum(r["kind"] == k for r in rows) for k in ("club", "national_team", "nation")}
    days = sum(r["date_precision"] == "day" for r in rows)
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}: {kinds}; exact dates: {days}; "
          f"with coordinates: {sum(bool(r['lat']) for r in rows)}")


def probe(ids: list[str]):
    """Diagnostics: how Wikidata records given items (classes, inception, English Wikipedia title)."""
    ents = entities(set(ids))
    for i in ids:
        e = ents.get(i, {})
        classes = [(c["mainsnak"].get("datavalue", {}).get("value", {}).get("id"), c.get("rank"))
                   for c in e.get("claims", {}).get("P31", [])]
        inc = [(c["mainsnak"].get("datavalue", {}).get("value", {}).get("time"),
                c["mainsnak"].get("datavalue", {}).get("value", {}).get("precision"), c.get("rank"))
               for c in e.get("claims", {}).get("P571", [])]
        print(f"{i} {label(e)!r}: P31={classes} P571={inc} enwiki={enwiki(e)!r} sitelinks={sitelinks(e)}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        probe(sys.argv[2].split(","))
    else:
        main()
