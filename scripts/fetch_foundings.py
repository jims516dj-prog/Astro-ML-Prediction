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
          "country", "aliases", "source"]

CLUBS = """SELECT ?item ?inc ?pr WHERE {
  ?item wdt:P31 wd:Q476028 ; p:P571/psv:P571 ?tv .
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


def entities(ids: set[str], props: str = "labels|aliases|claims") -> dict[str, dict]:
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
                                          f"wikidata:{i}"])))
        n = qid(r.get("nation", ""))
        nd, npr = date_of(r.get("ninc", ""), r.get("npr", ""))
        if kind == "national_team" and n and nd and npr and (i, "nation") not in seen:
            seen.add((i, "nation"))
            cap = next(iter(claim_ids(ents.get(n, {}), "P36")), "")
            lat, lon = coord(ents.get(cap))
            rows.append(dict(zip(FIELDS, [label(e) or i, "nation", nd, npr, "", label(ents.get(cap)), lat, lon,
                                          label(ents.get(n)), aliases(e), f"wikidata:{n}"])))
    rows.sort(key=lambda r: (r["team"].lower(), r["kind"]))
    return rows


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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    kinds = {k: sum(r["kind"] == k for r in rows) for k in ("club", "national_team", "nation")}
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}: {kinds}; "
          f"with coordinates: {sum(bool(r['lat']) for r in rows)}")


if __name__ == "__main__":
    main()
