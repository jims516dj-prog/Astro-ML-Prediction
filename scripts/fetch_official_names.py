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
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from astrofoot import foundings, geo, nations, teamnames  # noqa: E402
from fetch_founding_days import FOOTBALL, get, similar  # noqa: E402

BUDGET_S = 60 * 60
VERSION = 2          # entries made by an older version of the rules are redone (their item is kept)
START = time.time()


def entities(qids, labels=True):
    """Items by id; an item whose fetch failed is left out (the caller keeps what it had)."""
    out, failed = {}, 0
    step = 10 if labels else 40                       # big clubs' items in every language are large
    for i in range(0, len(qids), step):
        props = "claims|labels|aliases" if labels else "claims"
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=" + props + "&ids="
               + "|".join(qids[i:i + step]))
        d = get(url) or (time.sleep(20) or get(url, tries=4))
        if not d or "entities" not in d:
            failed += len(qids[i:i + step])
        out.update({q: e for q, e in ((d or {}).get("entities") or {}).items() if "missing" not in e})
        time.sleep(0.5)
    if failed:
        print(f"  {failed} item(s) could not be fetched; their clubs keep their earlier entry")
    return out


def claim_ids(e, prop):
    return [(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id")
            for c in (e.get("claims") or {}).get(prop, [])]


def is_latin(s: str) -> bool:
    """True when every letter is in the Latin script (name numerology reads Latin letters only)."""
    letters = [ch for ch in s or "" if ch.isalpha()]
    return bool(letters) and all("LATIN" in unicodedata.name(ch, "") for ch in letters)


def official(e):
    """(text, language) of the current official name in the Latin script, or (None, None)."""
    best = None
    for c in (e.get("claims") or {}).get("P1448", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if not v.get("text") or "P582" in (c.get("qualifiers") or {}):
            continue                                  # a former name (it has an end date)
        if not is_latin(v["text"]):
            continue                                  # Greek, Cyrillic, Chinese...: the Latin form is used
        rank = {"preferred": 0, "normal": 1}.get(c.get("rank"), 2)
        if best is None or rank < best[0]:
            best = (rank, v["text"], v.get("language"))
    return (best[1], best[2]) if best else (None, None)


def tidy(label: str) -> str:
    s = re.sub(r"\s*\((?:football club|soccer club|club|[A-Z][^)]*)\)$", "", label.strip())
    return re.sub(r"\b((?:[A-Z]\.){2,})", lambda m: m.group(1).replace(".", ""), s).strip()


def short_name(e, legal_lang):
    """The native short name when it is written in the Latin script, else the English label."""
    labels = e.get("labels") or {}
    pick = lambda lang: (v if is_latin(v := (labels.get(lang) or {}).get("value") or "") else None)  # noqa: E731
    en = pick("en") or pick("en-gb") or pick("mul")
    native = pick(legal_lang) if legal_lang else None
    if native and (not en or len(native) <= len(en) + 4):
        return tidy(native)
    return tidy(en or native or "")


def _words(s: str) -> set[str]:
    s = unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{3,}", s)} - {
        "club", "football", "futbol", "futebol", "fussball", "clube", "sport", "sporting", "calcio", "united", "city",
        "athletic", "deportivo", "real", "the", "and", "spor", "esporte"}


def names_agree(team: str, e) -> bool:
    """The item's labels or aliases (any language) share a name word with the team, or it is an initialism."""
    base = teamnames.split(team)[0]
    if re.fullmatch(r"[A-Z][A-Za-z]{1,4}", base) and sum(ch.isupper() for ch in base) >= 2:
        return True                                   # "KuPS", "SJK", "CSA": an initialism
    mine = _words(base)
    if not mine:
        return True
    theirs = set()
    for v in (e.get("labels") or {}).values():
        theirs |= _words(v.get("value"))
    for vs in (e.get("aliases") or {}).values():
        for v in vs:
            theirs |= _words(v.get("value"))
    theirs |= _words(official(e)[0] or "")
    return any(a == b or (len(min(a, b, key=len)) >= 3 and (a.startswith(b) or b.startswith(a)))
               for a in mine for b in theirs)


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
    clubs = {}
    for t, c in out.items():
        if not isinstance(t, str) or teamnames.nation(t):
            continue
        base = teamnames.split(t)[0]                  # "Celta B" is named through "Celta" (+ " B" on screen)
        clubs[base] = clubs.get(base) or c
    return clubs


def merge(theirs_file: str) -> None:
    """Merge the names file on main into this run's before publishing: a club named on either side stays named
    (the entry made under the current rules wins), so a run that started from an older copy, or whose lookups
    failed, never wipes names out."""
    mine = json.loads(teamnames.FILE.read_text()) if teamnames.FILE.exists() else {}
    try:
        theirs = json.loads(Path(theirs_file).read_text())
    except (OSError, ValueError):
        theirs = {}
    rank = lambda v: (bool((v or {}).get("short")), (v or {}).get("v") == VERSION)  # noqa: E731
    out = dict(theirs)
    for k, v in mine.items():
        if k not in out or rank(v) >= rank(out[k]):
            out[k] = v
    teamnames.FILE.write_text(json.dumps(out, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"merged: {sum(1 for v in out.values() if v.get('short'))} clubs named")


def main():
    cache = json.loads(teamnames.FILE.read_text()) if teamnames.FILE.exists() else {}
    month = time.strftime("%Y-%m")
    teams = teams_and_countries()
    for k in [k for k in cache if teamnames.split(k)[1] and not k.startswith("W:")]:
        del cache[k]                                  # reserve / youth sides go through their club
    cand = {t: [cache[t]["qid"]] for t in teams if (cache.get(t) or {}).get("qid")
            and cache[t].get("v") != VERSION}         # redo with the current rules, same item
    todo = sorted(t for t in teams if t in cand or (not (cache.get(t) or {}).get("short")
                                                     and (cache.get(t) or {}).get("tried") != month))
    print(f"{len(teams)} clubs; {len(todo)} to name ({len(cand)} redone under the current rules)")
    for t in todo:
        if t in cand:
            continue
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
        if cand.get(t) and not any(q in ents for q in cand[t]):
            continue                                  # the lookup failed: try again next run, keep the entry
        pick, why = None, ["no Wikidata item found"]
        for q in cand.get(t, []):
            e = ents.get(q) or {}
            if not set(claim_ids(e, "P31")) & FOOTBALL:
                why.append(f"{q}: not a football club")
                continue
            want = teams.get(t)
            have = {iso.get(c) for c in claim_ids(e, "P17")} - {None}
            if want and have and not (have & nations.SAME.get(want, {want})):
                why.append(f"{q}: in {sorted(have)}, not {want}")
                continue                              # a namesake in another country
            if not want and not have:
                why.append(f"{q}: no country to confirm with")
                continue                              # nothing to confirm the match with
            if not names_agree(t, e):
                print(f"  rejected {t} -> {q} {((e.get('labels') or {}).get('en') or {}).get('value')}: names differ")
                continue
            pick = (q, e)
            break
        if not pick:
            cache[t] = {"tried": month, "why": "; ".join(why[1:] or why)}
            continue
        q, e = pick
        legal, lang = official(e)
        short = short_name(e, lang)
        if not short:
            cache[t] = {"tried": month, "why": f"{q}: no Latin-script name"}
            continue
        cache[t] = {"short": short, "legal": legal or short, "qid": q, "v": VERSION}
        found += 1
    teamnames.FILE.parent.mkdir(parents=True, exist_ok=True)
    teamnames.FILE.write_text(json.dumps(cache, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"found {found} official names; {sum(1 for v in cache.values() if v.get('short'))} clubs named in all")
    for t in sorted(t for t in todo if (cache.get(t) or {}).get("short"))[:60]:
        print(f"  {t} -> {cache[t]['short']}  |  {cache[t]['legal']}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--merge":
        merge(sys.argv[2])
    else:
        main()
