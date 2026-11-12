"""Founding dates known to the day for the soccer day reading, from free sources (run on GitHub Actions):

1. Wikidata: the club's inception (P571) when recorded to the day.
2. Wikipedia: the infobox's founded / formed field in the club's article (English, then the local language editions)
   when Wikidata has only the year.
3. National teams: the founding date of the national football association (the team's operator in Wikidata), as
   sports sites such as Sofascore show it.

Teams already known to the day are left alone. Results go into data/ref/team_founding_days.json (team → date, name
and source), which the app reads. Wikipedia text is CC BY-SA; Wikidata is CC0."""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from astrofoot import foundings, teamday  # noqa: E402

UA = {"User-Agent": "astro-football-research/1.0 (personal research script; founding dates)"}
LANGS = ("en", "de", "es", "it", "fr", "pt", "nl", "tr", "el", "sv", "no", "da", "pl", "ro", "ru", "ja", "ko", "zh")
MONTHS = {
    "en": "january february march april may june july august september october november december",
    "de": "januar februar märz april mai juni juli august september oktober november dezember",
    "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
    "pt": "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro",
    "nl": "januari februari maart april mei juni juli augustus september oktober november december",
}
MONTH = {name: i + 1 for words in MONTHS.values() for i, name in enumerate(words.split())}
MONTH.update({m[:3]: i + 1 for i, m in enumerate(MONTHS["en"].split())})
FIELDS = r"(?:founded|formed|founded_date|foundation|established|fundación|fundacion|fundado|fundada|gegründet|" \
         r"gruendung|gründung|fondazione|fondation|fondé|fundação|fundacao|opgericht|opgericht_op|kuruluş|kurulus|" \
         r"grundad|grunnlagt|stiftet|założony|zalozony|înființat|основан|設立|창단|成立)"


FOOTBALL = {"Q476028", "Q6979593", "Q103229495", "Q15944511", "Q847017", "Q1194951"}   # club, national team, …


def similar(a: str, b: str) -> bool:
    import difflib
    na, nb = foundings._key(a), foundings._key(b)
    if not na or not nb:
        return False
    ta, tb = set(na.split()), set(nb.split())
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.8 or (len(ta) > 0 and ta <= tb and len(na) >= 4)


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            time.sleep(1 + 2 * i)
    return None


def wikidata(qids):
    out = {}
    for i in range(0, len(qids), 40):
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|sitelinks|labels&languages=en&ids="
                + "|".join(qids[i:i + 40]))
        out.update((d or {}).get("entities", {}))
        time.sleep(0.2)
    return out


def inception(ent):
    """Day-precision P571 of a Wikidata entity, or None."""
    for c in (ent.get("claims") or {}).get("P571", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if v.get("precision") == 11 and v.get("time"):
            t = v["time"].lstrip("+")[:10]
            if re.match(r"\d{4}-\d\d-\d\d$", t) and not t.endswith("-00"):
                return t
    return None


def parse_date(text: str) -> str | None:
    """A full date in an infobox value, in the usual templates and languages."""
    t = re.sub(r"<!--.*?-->|<ref.*?(</ref>|/>)", " ", text, flags=re.S)
    m = re.search(r"\{\{\s*(?:start[ _]date(?: and age)?|birth date|date de création|date|fecha|data|datum|dts)"
                  r"[^|}]*\|\s*(?:df=y\w*\s*\|\s*|mf=y\w*\s*\|\s*)?(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", t, re.I)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    low = t.lower().replace("º", "").replace("°", "").replace("1er", "1").replace(".", " ")
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zäöüéûçãõ]+)\s+(?:de\s+)?(\d{4})", low)
    if m and m.group(2) in MONTH:
        return f"{int(m.group(3)):04d}-{MONTH[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", low)
    if m and m.group(1) in MONTH:
        return f"{int(m.group(3)):04d}-{MONTH[m.group(1)]:02d}-{int(m.group(2)):02d}"
    return None


def infobox_date(lang, title):
    d = get(f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&prop=revisions"
            f"&rvprop=content&rvslots=main&redirects=1&titles=" + urllib.parse.quote(title))
    try:
        text = d["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    except (TypeError, KeyError, IndexError):
        return None
    for m in re.finditer(r"\|\s*" + FIELDS + r"\s*=\s*([^\n]+)", text, re.I):
        got = parse_date(m.group(1))
        if got and 1800 <= int(got[:4]) <= 2030:
            return got
    return None


def from_entity(ent):
    """(date, source) from Wikidata, then the Wikipedia infoboxes."""
    got = inception(ent)
    if got:
        return got, "wikidata"
    links = ent.get("sitelinks") or {}
    for lang in LANGS:
        sl = links.get(f"{lang}wiki")
        if sl:
            got = infobox_date(lang, sl["title"])
            time.sleep(0.1)
            if got:
                return got, f"wikipedia:{lang}"
    return None, None


def is_football(e: dict) -> bool:
    claims = e.get("claims") or {}
    kinds = {(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id") for c in claims.get("P31", [])}
    sport = {(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id") for c in claims.get("P641", [])}
    return bool(kinds & FOOTBALL) or "Q2736" in sport


def women_teams(cache: dict) -> dict:
    """Women's teams of the women's section (ESPN lists them by the club's plain name): their own founding dates,
    under 'W:<team>', never the men's club's."""
    from astrofoot import live
    try:
        recs = live.records(live.LEDGER / "women")
    except Exception as e:  # noqa: BLE001
        print("women's ledger unavailable:", e)
        return {}
    teams = sorted({t for r in recs for t in (r["home"], r["away"])})
    todo = [t for t in teams if not (cache.get(f"W:{t}") or {}).get("date")]
    print(f"women's section: {len(teams)} teams, {len(todo)} without a founding date known to the day")
    out = {}
    for t in todo:
        hit = None
        for q in (f"{t} women", f"{t} Women", f"{t} femenil", f"{t} femenino", f"{t} feminino", f"{t} frauen",
                  f"{t} femminile", f"{t} féminine", f"{t} ladies"):
            d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=6"
                    "&search=" + urllib.parse.quote(q))
            time.sleep(0.15)
            ids = [h["id"] for h in (d or {}).get("search", [])]
            if not ids:
                continue
            es = wikidata(ids)
            for qid in ids:
                e = es.get(qid) or {}
                label = ((e.get("labels") or {}).get("en") or {}).get("value") or next(
                    (h.get("label") for h in d["search"] if h["id"] == qid), "")
                base = foundings._key(t)
                if is_football(e) and teamday.WOMEN_WORDS.search(label or "") and base and \
                        set(base.split()) & set(foundings._key(label).split()):
                    hit = (qid, label, e)
                    break
            if hit:
                break
        if not hit:
            continue
        date, src = from_entity(hit[2])
        if date:
            out[f"W:{t}"] = {"date": date, "name": hit[1], "source": f"{src} ({hit[0]})"}
    print(f"women's teams: {len(out)} founding dates found")
    return out


def main():
    teams = set()
    w = Path("data/work/matches.parquet")
    if w.exists():
        m = pd.read_parquet(w, columns=["home", "away"])
        teams |= set(m.home) | set(m.away)
    try:
        from astrofoot import live
        teams |= {t for r in live.records() for t in (r["home"], r["away"])}
    except Exception as e:  # noqa: BLE001
        print("live record unavailable:", e)
    cache = json.loads(teamday.CACHE.read_text()) if teamday.CACHE.exists() else {}
    todo = sorted(t for t in teams if not (cache.get(t) or {}).get("date"))
    women_found = women_teams(cache)
    print(f"{len(teams)} teams; {len(todo)} without a founding date known to the day")
    cand = {}
    for t in todo:
        c = [x for x in foundings.search(t, limit=4) if x["match"] in ("exact", "alias")]
        if c and str(c[0].get("source", "")).startswith("wikidata:"):
            cand[t] = c[0]
    # teams the founding table does not know: Wikidata's own search, kept only for a football club or national
    # team whose name closely matches
    rest = [t for t in todo if t not in cand]
    print(f"searching Wikidata for {len(rest)} teams the founding table does not match")
    for t in rest:
        d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=5"
                "&search=" + urllib.parse.quote(t))
        hits = [h["id"] for h in (d or {}).get("search", [])]
        time.sleep(0.15)
        if not hits:
            continue
        es = wikidata(hits)
        for q in hits:
            e = es.get(q) or {}
            kinds = {(((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id")
                     for c in (e.get("claims") or {}).get("P31", [])}
            label = ((e.get("labels") or {}).get("en") or {}).get("value") or next(
                (h.get("label") for h in d["search"] if h["id"] == q), "")
            if kinds & FOOTBALL and similar(t, label):
                cand[t] = {"team": label or t, "kind": "national_team" if "Q6979593" in kinds else "club",
                           "source": f"wikidata:{q}"}
                break
    qids = sorted({c["source"].split(":", 1)[1] for c in cand.values()})
    print(f"{len(cand)} matched to a Wikidata item; fetching {len(qids)} items")
    ents = wikidata(qids)
    # national teams: their association (operator P137 / owned by P127) carries the founding date
    ops = {}
    for t, c in cand.items():
        if c.get("kind") == "national_team":
            e = ents.get(c["source"].split(":", 1)[1]) or {}
            for p in ("P137", "P127", "P1830"):
                for cl in (e.get("claims") or {}).get(p, []):
                    q = (((cl.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}).get("id")
                    if q:
                        ops[t] = q
                        break
                if t in ops:
                    break
    op_ents = wikidata(sorted(set(ops.values()))) if ops else {}
    found = {}
    for n, (t, c) in enumerate(sorted(cand.items())):
        q = c["source"].split(":", 1)[1]
        date, src = (None, None)
        if t in ops and ops[t] in op_ents:
            date, src = from_entity(op_ents[ops[t]])
            src = src and f"association, {src}"
        if not date:
            date, src = from_entity(ents.get(q) or {})
        if date:
            found[t] = {"date": date, "name": c["team"], "source": f"{src} ({q})"}
        if n % 100 == 0:
            print(f"  {n}/{len(cand)}: {len(found)} found")
    cache.update(found)
    cache.update(women_found)
    teamday.CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))
    by = {}
    for v in found.values():
        k = v["source"].split(" (")[0]
        by[k] = by.get(k, 0) + 1
    print(f"found {len(found)} new founding dates: {by}")
    print(f"teams with a date known to the day: {sum(1 for t in teams if (cache.get(t) or {}).get('date'))} of {len(teams)}")


if __name__ == "__main__":
    main()
