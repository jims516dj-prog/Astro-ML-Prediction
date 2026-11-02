"""Build data/ref/team_foundings.csv from Wikidata (CC0): founding dates of football clubs,
national teams and the nations they represent.

  python scripts/fetch_foundings.py            # needs access to query.wikidata.org

One row per (team, chart kind). Kinds:
  club                 inception (P571) of an association football club
  national_team        inception of a national association football team
  nation               inception of the country the national team represents (Rao's "nation chart")
Founding place: location of formation (P740), else headquarters (P159), else home venue (P115),
else the administrative area (P131): the first one with coordinates.
Dates come with Wikidata's precision (day / month / year). Times are essentially never recorded,
so `founded_time` is left blank: add known times by hand in the app (they are saved as overrides).
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
ENDPOINT = "https://query.wikidata.org/sparql"
UA = "astro-football-research/1.0 (https://github.com/jims516dj-prog/Astro-ML-Prediction)"
PRECISION = {"11": "day", "10": "month", "9": "year"}
YEAR_CHUNKS = [(1800, 1880), (1880, 1900), (1900, 1915), (1915, 1930), (1930, 1950), (1950, 1970),
               (1970, 1990), (1990, 2005), (2005, 2100)]

PLACE = """
  OPTIONAL { ?item wdt:P740 ?p1 . ?p1 wdt:P625 ?c1 }
  OPTIONAL { ?item wdt:P159 ?p2 . ?p2 wdt:P625 ?c2 }
  OPTIONAL { ?item wdt:P115 ?p3 . ?p3 wdt:P625 ?c3 }
  OPTIONAL { ?item wdt:P131 ?p4 . ?p4 wdt:P625 ?c4 }
  BIND(COALESCE(?c1, ?c2, ?c3, ?c4) AS ?coord)
  BIND(COALESCE(?p1, ?p2, ?p3, ?p4) AS ?place)
"""

CLUBS = """
SELECT ?item (SAMPLE(?lbl) AS ?label) (SAMPLE(?inc) AS ?inception) (SAMPLE(?pr) AS ?prec)
       (SAMPLE(?ctryLbl) AS ?country) (SAMPLE(?placeLbl) AS ?placeName) (SAMPLE(?coord) AS ?coords)
       (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
WHERE {
  ?item wdt:P31 wd:Q476028 ; p:P571/psv:P571 ?tv .
  ?tv wikibase:timeValue ?inc ; wikibase:timePrecision ?pr .
  FILTER(YEAR(?inc) >= %d && YEAR(?inc) < %d && ?pr >= 9)
  ?item rdfs:label ?lbl . FILTER(LANG(?lbl) = "en")
  OPTIONAL { ?item wdt:P17 ?ctry . ?ctry rdfs:label ?ctryLbl . FILTER(LANG(?ctryLbl) = "en") }
  %s
  OPTIONAL { ?place rdfs:label ?placeLbl . FILTER(LANG(?placeLbl) = "en") }
  OPTIONAL { ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "en") }
}
GROUP BY ?item
"""

NATIONAL = """
SELECT ?item (SAMPLE(?lbl) AS ?label) (SAMPLE(?inc) AS ?inception) (SAMPLE(?pr) AS ?prec)
       (SAMPLE(?ctryLbl) AS ?country) (SAMPLE(?placeLbl) AS ?placeName) (SAMPLE(?coord) AS ?coords)
       (SAMPLE(?nation) AS ?nationItem) (SAMPLE(?ninc) AS ?nationInception) (SAMPLE(?npr) AS ?nationPrec)
       (SAMPLE(?capLbl) AS ?capitalName) (SAMPLE(?capCoord) AS ?capitalCoords)
       (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
WHERE {
  ?item wdt:P31 wd:Q6979593 .
  ?item rdfs:label ?lbl . FILTER(LANG(?lbl) = "en")
  OPTIONAL { ?item p:P571/psv:P571 ?tv . ?tv wikibase:timeValue ?inc ; wikibase:timePrecision ?pr . }
  OPTIONAL { ?item wdt:P1532 ?nation . ?nation rdfs:label ?ctryLbl . FILTER(LANG(?ctryLbl) = "en")
             OPTIONAL { ?nation p:P571/psv:P571 ?ntv . ?ntv wikibase:timeValue ?ninc ; wikibase:timePrecision ?npr . }
             OPTIONAL { ?nation wdt:P36 ?cap . ?cap wdt:P625 ?capCoord .
                        ?cap rdfs:label ?capLbl . FILTER(LANG(?capLbl) = "en") } }
  %s
  OPTIONAL { ?place rdfs:label ?placeLbl . FILTER(LANG(?placeLbl) = "en") }
  OPTIONAL { ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "en") }
}
GROUP BY ?item
"""


def sparql(query: str, retries: int = 4) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 - WDQS throttles and times out; back off and retry
            print(f"  attempt {attempt + 1} failed: {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise SystemExit("Wikidata query failed repeatedly")


def val(b: dict, k: str) -> str:
    return b[k]["value"] if k in b else ""


def point(s: str):
    """'Point(lon lat)' -> (lat, lon)."""
    if not s.startswith("Point("):
        return "", ""
    lon, lat = s[6:-1].split()
    return f"{float(lat):.5f}", f"{float(lon):.5f}"


def row(team, kind, qid, inception, prec, place, coords, country, aliases):
    lat, lon = point(coords)
    p = PRECISION.get(prec, "")
    return {"team": team, "kind": kind, "founded_date": inception[:10].lstrip("+") if inception else "",
            "date_precision": p, "founded_time": "", "place": place, "lat": lat, "lon": lon,
            "country": country, "aliases": aliases, "source": f"wikidata:{qid}"}


def main():
    rows = []
    for lo, hi in YEAR_CHUNKS:
        print(f"clubs founded {lo}-{hi - 1} ...", flush=True)
        for b in sparql(CLUBS % (lo, hi, PLACE)):
            qid = val(b, "item").rsplit("/", 1)[-1]
            rows.append(row(val(b, "label"), "club", qid, val(b, "inception"), val(b, "prec"),
                            val(b, "placeName"), val(b, "coords"), val(b, "country"), val(b, "aliases")))
        time.sleep(2)
    print("national teams and nations ...", flush=True)
    for b in sparql(NATIONAL % PLACE):
        qid = val(b, "item").rsplit("/", 1)[-1]
        label, country, aliases = val(b, "label"), val(b, "country"), val(b, "aliases")
        if val(b, "inception"):
            rows.append(row(label, "national_team", qid, val(b, "inception"), val(b, "prec"),
                            val(b, "placeName"), val(b, "coords"), country, aliases))
        if val(b, "nationInception"):
            nq = val(b, "nationItem").rsplit("/", 1)[-1]
            rows.append(row(label, "nation", nq, val(b, "nationInception"), val(b, "nationPrec"),
                            val(b, "capitalName"), val(b, "capitalCoords"), country, aliases))
    rows = [r for r in rows if r["founded_date"] and r["date_precision"]]
    rows.sort(key=lambda r: (r["team"].lower(), r["kind"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    kinds = {k: sum(r["kind"] == k for r in rows) for k in ("club", "national_team", "nation")}
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}: {kinds}")


if __name__ == "__main__":
    main()
