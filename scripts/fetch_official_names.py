"""Official club names from Wikidata (run on GitHub Actions), for display and name numerology.

For each club the app knows (history and live record), the club's Wikidata item is found (the founding table's
match, else Wikidata's search kept only for a football club whose name is close), and checked against the club's
country (the league's country, or the country of the ground of its home games) so that a namesake abroad is never
taken. From the item:

- legal: its official name (P1448), current value (no end date; preferred rank first): "Futbol Club Barcelona",
  "Fußball-Club Bayern München e. V.". Used for name numerology.
- short: the name the club is registered and listed under: its label in the language of the official name when that
  is a short form ("FC Bayern München"), else its English label ("FC Barcelona"), with initialisms closed up
  ("Manchester United F.C." -> "Manchester United FC"). Shown on screen.

National teams are not looked up: they use FIFA's names (astrofoot/teamnames.py). Clubs already matched are kept;
clubs not matched are tried again next month. Results go into data/ref/team_names.json. Wikidata is CC0."""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from astrofoot import foundings, geo, nations, teamnames  # noqa: E402
from fetch_founding_days import FOOTBALL, get, similar  # noqa: E402

BUDGET_S = 60 * 60
START = time.time()


def entities(qids, labels=True):
    out = {}
    for i in range(0, len(qids), 40):
        props = "claims|labels" if labels else "claims"
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=" + props + "&ids="
                + "|".join(qids[i:i + 40]))
        out.update((d or {}).get("entities") or {})
        time.sleep(0.2)
    return out


def claim_ids(e, prop):
    return [(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id")
            for c in (e.get("claims") or {}).get(prop, [])]


def official(e):
    """(text, language) of the current official name, or (None, None)."""
    best = None
    for c in (e.get("claims") or {}).get("P1448", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if not v.get("text") or "P582" in (c.get("qualifiers") or {}):
            continue                                  # a former name (it has an end date)
        rank = {"preferred": 0, "normal": 1}.get(c.get("rank"), 2)
        if best is None or rank < best[0]:
            best = (rank, v["text"], v.get("language"))
    return (best[1], best[2]) if best else (None, None)


def tidy(label: str) -> str:
    s = re.sub(r"\s*\((?:football club|soccer club|club|[A-Z][^)]*)\)$", "", label.strip())
    return re.sub(r"\b((?:[A-Z]\.){2,})", lambda m: m.group(1).replace(".", ""), s).strip()


def short_name(e, legal_lang):
    labels = e.get("labels") or {}
    en = (labels.get("en") or {}).get("value")
    native = (labels.get(legal_lang) or {}).get("value") if legal_lang else None
    if native and (not en or len(native) <= len(en) + 4):
        return tidy(native)
    return tidy(en or native or "")


def teams_and_countries():
    """{team: ISO code or None} for every club in the history and the live records (men's)."""
    out = {}
    w = Path("data/work/matches.parquet")
    if w.exists():
        m = pd.read_parquet(w, columns=["division", "home", "away"])
        for div, h, a in m.itertuples(index=False):
            c = geo.DIVISION_COUNTRY.get(div)
            for t in (h, a):
                out.setdefault(t, c)
    try:
        from astrofoot import live
        for r in live.read_predictions():
            c = geo.DIVISION_COUNTRY.get(r["division"])
            if not c and r.get("venue_lat") is not None and r["division"] not in live.MULTI_CLUB:
                c = nations.country_at(r["venue_lat"], r["venue_lon"])   # the home side's ground
            out[r["home"]] = out.get(r["home"]) or c
            out.setdefault(r["away"], None)
    except Exception as e:  # noqa: BLE001
        print("live record unavailable:", e)
    return {t: c for t, c in out.items() if isinstance(t, str) and not teamnames.nation(t)}


def main():
    cache = json.loads(teamnames.FILE.read_text()) if teamnames.FILE.exists() else {}
    month = time.strftime("%Y-%m")
    teams = teams_and_countries()
    todo = sorted(t for t in teams if not (cache.get(t) or {}).get("short") and (cache.get(t) or {}).get("tried") != month)
    print(f"{len(teams)} clubs; {len(todo)} without an official name yet")
    cand = {}
    for t in todo:
        base = teamnames.split(t)[0]
        c = [x for x in foundings.search(base, limit=4) if x["match"] in ("exact", "alias")]
        if c and str(c[0].get("source", "")).startswith("wikidata:"):
            cand[t] = [c[0]["source"].split(":", 1)[1]]
    rest = [t for t in todo if t not in cand]
    print(f"searching Wikidata for {len(rest)} clubs the founding table does not match")
    for t in rest:
        if time.time() - START > BUDGET_S / 2:
            print("  search budget reached; the rest wait for the next run")
            break
        d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=5"
                "&search=" + urllib.parse.quote(teamnames.split(t)[0]))
        hits = [h["id"] for h in (d or {}).get("search", [])
                if similar(teamnames.split(t)[0], h.get("label") or "") or similar(t, h.get("label") or "")]
        time.sleep(0.15)
        if hits:
            cand[t] = hits
    qids = sorted({q for qs in cand.values() for q in qs})
    print(f"{len(cand)} clubs with candidates; fetching {len(qids)} items")
    ents = entities(qids)
    countries = sorted({c for e in ents.values() for c in claim_ids(e, "P17") if c})
    iso = {}
    for q, e in entities(countries, labels=False).items():
        for c in (e.get("claims") or {}).get("P297", []):
            iso[q] = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
    found = 0
    for t in todo:
        pick = None
        for q in cand.get(t, []):
            e = ents.get(q) or {}
            if not set(claim_ids(e, "P31")) & FOOTBALL:
                continue
            want = teams.get(t)
            have = {iso.get(c) for c in claim_ids(e, "P17")} - {None}
            if want and have and not (have & nations.SAME.get(want, {want})):
                continue                              # a namesake in another country
            if not want and not have:
                continue                              # nothing to confirm the match with
            pick = (q, e)
            break
        if not pick:
            cache[t] = {"tried": month}
            continue
        q, e = pick
        legal, lang = official(e)
        short = short_name(e, lang)
        if not short:
            cache[t] = {"tried": month}
            continue
        cache[t] = {"short": short, "legal": legal or short, "qid": q}
        found += 1
    teamnames.FILE.parent.mkdir(parents=True, exist_ok=True)
    teamnames.FILE.write_text(json.dumps(cache, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"found {found} official names; {sum(1 for v in cache.values() if v.get('short'))} clubs named in all")
    for t in sorted(t for t in todo if (cache.get(t) or {}).get("short"))[:60]:
        print(f"  {t} -> {cache[t]['short']}  |  {cache[t]['legal']}")


if __name__ == "__main__":
    main()
