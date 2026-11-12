"""Tennis players' full legal names from Wikidata (run on GitHub Actions), for name numerology.

On screen players keep the name their tour lists them under (ATP / WTA through ESPN; Challenger and ITF through the
Live Tennis API), one name per player. Behind the scenes the day reading's name numerology uses the full legal name:
the player's birth name in Wikidata (P1477), e.g. "Rafael Nadal Parera", "Carlos Alcaraz Garfia".

Matching is strict: the same date of birth and the same player by name (same surname and first name), and only when
exactly one Wikidata tennis player fits. Results go into data/ref/tennis_names.json ({player id: {legal, qid,
label}}); players not matched keep their tour name. Wikidata is CC0."""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from astrofoot.tennis import astro_num as an  # noqa: E402
from astrofoot.tennis import live as tlive  # noqa: E402
from astrofoot.tennis import names as tnames  # noqa: E402
from astrofoot.tennis.odds import same_player  # noqa: E402
from fetch_founding_days import get  # noqa: E402

SPARQL = "https://query.wikidata.org/sparql?format=json&query="
QUERY = """SELECT ?p ?label ?dob ?birth WHERE {{
  ?p wdt:P106 wd:Q10833314; wdt:P569 ?dob.
  FILTER(?dob >= "{a}-01-01T00:00:00Z"^^xsd:dateTime && ?dob < "{b}-01-01T00:00:00Z"^^xsd:dateTime)
  OPTIONAL {{ ?p wdt:P1477 ?birth. }}
  OPTIONAL {{ ?p rdfs:label ?label. FILTER(LANG(?label) = "en") }}
}}"""


def wikidata_players(first: int, last: int) -> dict[str, list[dict]]:
    """{date of birth: [{qid, label, birth}]} for tennis players born in these years."""
    out: dict[str, dict] = {}
    for y in range(first, last + 1):
        d = get(SPARQL + urllib.parse.quote(QUERY.format(a=y, b=y + 1)))
        for b in ((d or {}).get("results") or {}).get("bindings", []):
            q = b["p"]["value"].rsplit("/", 1)[-1]
            rec = out.setdefault(q, {"qid": q, "dob": b["dob"]["value"][:10], "label": None, "birth": set()})
            if "label" in b:
                rec["label"] = b["label"]["value"]
            if "birth" in b:
                rec["birth"].add(b["birth"]["value"])
        time.sleep(1.0)                               # the public endpoint's fair use
    by_dob: dict[str, list[dict]] = {}
    for r in out.values():
        by_dob.setdefault(r["dob"], []).append(r)
    return by_dob


def surname_words(name: str) -> set[str]:
    return {w for w in re.split(r"[\s\-]+", an.latin(name).lower()) if len(w) > 1}


def full_name(tour_name: str, births) -> str | None:
    """The birth name, only when it still carries the player's current surname: a player who took a married name
    ("Tatjana Maria", born Malek; "Alison Riske-Amritraj", born Riske) is known legally by that name now, so her
    tour name is kept."""
    mine = surname_words(tour_name.split()[-1])
    for b in sorted(b for b in births if an.latin(b).strip()):
        if mine and mine <= surname_words(b):
            return b
    return None


def main():
    pl = tlive.load_players(raw=True)
    pl = pl[pl.dob.notna()]
    years = sorted({int(str(d)[:4]) for d in pl.dob if an.clean_dob(d)})
    print(f"{len(pl)} players with a date of birth, born {years[0]}-{years[-1]}")
    by_dob = wikidata_players(years[0], years[-1])
    print(f"{sum(len(v) for v in by_dob.values())} tennis players in Wikidata for those years")
    out, ambiguous = {}, 0
    for r in pl.to_dict("records"):
        dob = an.clean_dob(r["dob"])
        cands = [c for c in by_dob.get(dob, []) if c["label"] and same_player(r["name"], c["label"])]
        if len(cands) != 1:
            ambiguous += len(cands) > 1
            continue
        c = cands[0]
        legal = full_name(r["name"], c["birth"])
        out[str(r["id"])] = {"qid": c["qid"], "label": c["label"], "legal": legal}
    tnames.FILE.parent.mkdir(parents=True, exist_ok=True)
    tnames.FILE.write_text(json.dumps(out, indent=0, sort_keys=True, ensure_ascii=False))
    with_legal = {k: v for k, v in out.items() if v.get("legal")}
    print(f"matched {len(out)} players ({ambiguous} ambiguous left out); {len(with_legal)} with a legal (birth) name")
    for k, v in list(with_legal.items())[:40]:
        print(f"  {k}: {v['label']}  |  {v['legal']}")


if __name__ == "__main__":
    main()
