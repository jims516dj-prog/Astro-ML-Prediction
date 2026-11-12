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
VERSION = 8          # unnamed clubs decided under an older version of the rules are tried again
NAMED_SINCE = 6      # named clubs are redone only when named under an older version than this
DOMINANCE = 2.0      # a close spelling is taken only when it is this many times as prominent as the next one
SHARED = {"US": {"CA"}, "CH": {"LI"}, "FR": {"MC"}, "ES": {"AD"}, "IE": {"GB"}, "GB": {"IE"}, "IT": {"SM"}}
TABLE_COUNTRY = {"People's Republic of China": "CN", "United States": "US", "Russia": "RU", "United Kingdom": "GB", "Kingdom of the Netherlands": "NL", "England": "GB", "Scotland": "GB",
                 "Wales": "GB", "Northern Ireland": "GB"}
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


_PLACES: dict = {}


def _coord(e):
    for c in (e.get("claims") or {}).get("P625", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if "latitude" in v:
            return v["latitude"], v["longitude"]
    return None


def item_location(e):
    """(lat, lon) of a club: its own coordinates, else its home ground's (P115), else its seat's (P159)."""
    ll = _coord(e)
    if ll:
        return ll
    for prop in ("P115", "P159"):
        ids = [q for q in claim_ids(e, prop) if q]
        missing = [q for q in ids if q not in _PLACES]
        if missing:
            _PLACES.update({q: _coord(x) for q, x in entities(missing, labels=False).items()})
        for q in ids:
            if _PLACES.get(q):
                return _PLACES[q]
    return None


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


def _fold(s: str) -> str:
    """Lower case, accents off, and the letters that do not decompose spelled out ("Zagłębie" -> "zaglebie")."""
    s = (s or "").lower()
    for a, b in (("ł", "l"), ("ø", "o"), ("æ", "ae"), ("œ", "oe"), ("ß", "ss"), ("đ", "d"), ("ı", "i"), ("þ", "th")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _words(s: str) -> set[str]:
    s = _fold(s)
    return {w for w in re.findall(r"[a-z]{3,}", s)} - {
        "club", "football", "futbol", "futebol", "fussball", "clube", "sport", "sporting", "calcio", "united", "city",
        "athletic", "deportivo", "real", "the", "and", "spor", "esporte"}


def _agrees(a: str, b: str) -> bool:
    """Two names share a word (prefix, close spelling or contraction allowed), or one is an initialism."""
    base = teamnames.split(a)[0]
    if re.fullmatch(r"[A-Z][A-Za-z]{1,4}", base) and sum(ch.isupper() for ch in base) >= 2:
        return True
    mine, theirs = _words(base), _words(b)
    return not mine or any(_abbrev_ok(w, theirs) for w in mine)


def names_agree(team: str, e, strict: bool = False) -> bool:
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
    plain = re.sub(r"\b(?:A\.?F\.?C|F\.?C|C\.?F|C\.?D|S\.?C|A\.?C|U\.?D|S\.?D|F\.?K|S\.?K|N\.?K)\b\.?", " ", base)
    initials = {ch.lower() for ch in re.findall(r"(?<![A-Za-z])([A-Z])(?:\.|\b)(?![A-Za-z])", plain)}
    if initials and not all(any(w.startswith(i) for w in theirs) for i in initials):
        return False                                  # "T. Moscow" is Torpedo, not Spartak
    if strict:                                        # every word: "Volga N. Novgorod" is not FC Nizhny Novgorod
        return all(_abbrev_ok(a, theirs) for a in mine)
    return any(_abbrev_ok(a, theirs) for a in mine)   # "nykoebing" ~ "nykobing", "dynamo" ~ "dinamo"


def competition_country(division: str) -> str | None:
    """ISO code of a domestic competition's country, from its name ("Oman: FA Cup", "Germany Amateur: Bayernliga",
    "England FA Cup"); None for an international one ("International: ...", "World: ...", "UEFA ...")."""
    from astrofoot import dataset
    from astrofoot.live import team_identity
    name = dataset.league_name(division) or ""
    if ":" in name:
        heads = [re.sub(r"\s+Amateur$", "", name.split(":", 1)[0].strip())]
    else:
        words = name.split()
        heads = [" ".join(words[:i]) for i in range(min(3, len(words) - 1), 0, -1)]
    for h in heads:
        if re.match(r"(?i)(international|world|uefa|caf|concacaf|conmebol|afc|club|africa|europe|asia)\b", h):
            return None
        code = team_identity(h)[0]
        if code:
            return "GB" if code.startswith("GB-") else code
    return None


def _abbrev_ok(word: str, theirs: set[str]) -> bool:
    """"rvs" ~ "rovers", "atl" ~ "atletico", "dynamo" ~ "dinamo", "go" ~ "goianiense": a prefix, a close spelling or
    an in-order contraction (same first letter)."""
    import difflib
    for t in theirs:
        if t.startswith(word) or (len(t) >= 3 and word.startswith(t)):
            return True
        if (len(word) >= 4 and word[0] == t[0] and abs(len(word) - len(t)) <= 1
                and difflib.SequenceMatcher(None, word, t).ratio() >= 0.8):    # "dynamo" ~ "dinamo", not "remo" ~ "gremio"
            return True
        if len(word) >= 3 and word[0] == t[0]:
            it = iter(t)
            if all(ch in it for ch in word):
                return True
    return False


def _tokens(s: str) -> set[str]:
    """Name words for matching, two-letter ones included ("Atletico GO", "Botafogo RJ")."""
    s = _fold(s).replace("&", "").replace(".", "").replace("'", "").replace("\u2019", "")
    return {w for w in re.findall(r"[a-z]{2,}", s)} - {
        "fc", "cf", "sc", "ac", "cd", "club", "football", "futbol", "futebol", "fussball", "clube", "the", "and", "de",
        "do", "da", "la", "el", "al", "of", "y", "e"}


def same_country(want: str | None, have: set) -> bool:
    """A club playing in this country's competitions may be registered next door: Toronto and Vancouver in MLS,
    Vaduz in Switzerland, Monaco in France, Derry City in Ireland, FC Andorra in Spain, Welsh clubs in England."""
    if not want or not have:
        return True
    ok = set(nations.SAME.get(want, {want})) | SHARED.get(want, set())
    return bool(set(have) & ok)


def _row_words(source: str) -> set[str]:
    from astrofoot import foundings as fd
    t = fd.table()
    if not len(t):
        return set()
    if "_by_source" not in _row_words.__dict__:
        _row_words._by_source = {s: names for s, names in zip(t.source, t.names)}
    out = set()
    for n in _row_words._by_source.get(source, []):
        out |= _words(n)
    return out


RESERVE_ITEM = re.compile(r"(?i)(-2\b|\bII\b|\bB\b$|\bU-?\d{2}\b|\breserves?\b|\bwomen\b|\bfeminin|\bladies\b)")


WOMEN_NAME = re.compile(r"(?i)\b(women|ladies|f[eé]minin\w*|lyonnes|frauen|damen|kvinner|dam)\b")


def _row_ok(source: str, mine: set[str]) -> bool:
    """The team's words are found in one of the table row's names, and that name belongs with the row's own label
    (a row whose alias is another club's name, e.g. "Olimpo de Bahia Blanca" on "Sarmiento", does not count)."""
    from astrofoot import foundings as fd
    t = fd.table()
    if "_rows" not in _row_ok.__dict__:
        _row_ok._rows = {s: names for s, names in zip(t.source, t.names)} if len(t) else {}
    names = _row_ok._rows.get(source) or []
    if not names:
        return False
    main = _tokens(names[0])
    for i, n in enumerate(names):
        words = _tokens(n)
        if all(_abbrev_ok(w, words) for w in mine) and (i == 0 or words & main or
                                                          any(_abbrev_ok(w, main) for w in words)):
            return True
    return False


HOME_AT: dict[str, list] = {}     # team -> home-game venues in the live record
HOME_DIV: dict[str, str] = {}     # team -> a division it hosted games in (history)
NEAR_KM = 40


def home_location(team: str):
    """(lat, lon) where the club plays its home games: its venues in the live record, else its stadium or
    curated home city (geo.resolve; a city guessed from the name only when nothing better is known)."""
    import statistics
    v = HOME_AT.get(team)
    if v:
        return statistics.median(x[0] for x in v), statistics.median(x[1] for x in v)
    if team in HOME_DIV:
        try:
            got = geo.resolve(team, HOME_DIV[team])
        except (OSError, ValueError):                 # venue tables not downloaded: no location
            got = None
        if got:
            return got[0], got[1]
    return None


def _km(a, b) -> float:
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(min(1.0, math.sqrt(h)))


def _row_names(source: str) -> list[str]:
    _row_ok(source, set())                            # builds the index
    return _row_ok._rows.get(source) or []


def _initials_ok(abbr: str, names: list[str]) -> bool:
    """"HJK" is one of the club's names, or the initials of one ("Helsingin Jalkapalloklubi")."""
    a = abbr.lower()
    for n in names:
        w = re.findall(r"[a-z]+", _fold(n))
        if a in w or "".join(x[0] for x in w).startswith(a):
            return True
        # initials that run into a compound word: "VPS" = Vaasan PalloSeura, "HJK" = Helsingin JalkapalloKlubi
        if len(w) >= 2 and len(a) > len(w) and a[0] == w[0][0] and a[1] == w[1][0]:
            rest = iter("".join(w[1:])[1:])
            if all(ch in rest for ch in a[2:]):
                return True
    return False


def nearby(mine: set[str], at, initialism: bool, want: str | None = None, abbr: str = "") -> list[dict]:
    """The table's clubs based within NEAR_KM of the club's home whose names carry its words (abbreviations
    allowed: "M'gladbach" -> Borussia Mönchengladbach)."""
    from astrofoot import foundings as fd
    import numpy as np
    t = fd.table()
    if "_arr" not in nearby.__dict__:
        lat = pd.to_numeric(t.lat, errors="coerce").to_numpy()
        lon = pd.to_numeric(t.lon, errors="coerce").to_numpy()
        nearby._arr = (lat, lon)
    lat, lon = nearby._arr
    d = 6371 * np.hypot(np.radians(lat - at[0]), np.radians(lon - at[1]) * np.cos(np.radians(at[0])))
    out = []
    for i in np.where(d <= NEAR_KM)[0]:
        r = t.iloc[i]
        if r.kind != "club" or not str(r.source).startswith("wikidata:") or RESERVE_ITEM.search(r.team or ""):
            continue
        c = TABLE_COUNTRY.get(r.country) or nations.code_of(r.country or "")
        if want and c and not same_country(want, {c}):
            continue                                  # across a border: Helsingør is not Helsingborg
        if (_initials_ok(abbr, r.names) if initialism else _row_ok(r.source, mine)):
            out.append({**fd._from_table(r), "match": "close"})
    return out


def namesakes(mine: set[str], want: str | None) -> list[dict]:
    """Every club in the table, in the team's country, whose names carry all of the team's words ("Zaglebie":
    Zagłębie Lubin and Zagłębie Sosnowiec), so a namesake the name search did not return still counts."""
    from astrofoot import foundings as fd
    if not want or not mine:
        return []
    t = fd.table()
    if "_idx" not in namesakes.__dict__:
        namesakes._idx = []
        for r in t.itertuples():
            if r.kind == "club" and str(r.source).startswith("wikidata:"):
                toks = set().union(*(_tokens(n) for n in r.names)) if r.names else set()
                namesakes._idx.append((toks, r))
    out = []
    for toks, r in namesakes._idx:
        if mine <= toks:
            c = TABLE_COUNTRY.get(r.country) or nations.code_of(r.country or "")
            if c and same_country(want, {c}):
                out.append({**fd._from_table(r), "match": "close"})
    return out


def table_candidates(team: str, want: str | None) -> tuple[list[str], str | None]:
    """(Wikidata item, the club's country) from the founding table, or ([], None).

    The candidates are the table's clubs in the team's country (when known) whose names carry the team's words
    ("Bielefeld" -> Arminia Bielefeld, "Bristol Rvs" -> Bristol Rovers, "Guimaraes" -> Vitória S.C. through its
    aliases); the most prominent is taken only when it clearly stands out (DOMINANCE times the next by Wikipedia
    editions), and a close spelling only for a club with an article in 10 or more of them."""
    base = teamnames.split(team)[0]
    if WOMEN_NAME.search(base):
        return [], None                               # a women's side under its own name: not the men's club
    iso = lambda x: TABLE_COUNTRY.get(x.get("country")) or nations.code_of(x.get("country") or "")  # noqa: E731
    initialism = bool(re.fullmatch(r"[A-Z]{2,5}", base))
    mine = _tokens(base)
    if not mine:
        return [], None
    pool = []
    for x in foundings.search(base, limit=12) + namesakes(mine, want):
        if not str(x.get("source", "")).startswith("wikidata:") or x.get("kind") != "club":
            continue
        if RESERVE_ITEM.search(x.get("team") or ""):
            continue                                  # a reserve, youth or women's side
        c = iso(x)
        if want and c and not same_country(want, {c}):
            continue
        if not want and not c:
            continue
        if not (_initials_ok(base, _row_names(x["source"])) if initialism else _row_ok(x["source"], mine)):
            continue
        pool.append(x)
    at = home_location(team)
    if at:
        pool += nearby(mine, at, initialism, want, base)
    if not pool:
        return [], None
    pool = list({x["source"]: x for x in pool}.values())
    pool.sort(key=lambda x: -int(x.get("sitelinks") or 0))
    top, links = pool[0], int(pool[0].get("sitelinks") or 0)
    second = int(pool[1].get("sitelinks") or 0) if len(pool) > 1 else 0
    if links >= max(DOMINANCE * second, 1) and (top["match"] != "close" or links >= 10):
        return [top["source"].split(":", 1)[1]], want or iso(top)
    if at:
        # namesakes of similar standing ("Zaglebie": Lubin or Sosnowiec): the one based where the club plays
        near = [x for x in pool if x.get("lat") is not None and _km(at, (x["lat"], x["lon"])) <= NEAR_KM]
        near.sort(key=lambda x: -int(x.get("sitelinks") or 0))
        if near:
            n1 = int(near[0].get("sitelinks") or 0)
            n2 = int(near[1].get("sitelinks") or 0) if len(near) > 1 else 0
            if n1 >= max(DOMINANCE * n2, 10):          # a professional club: small namesakes are not guessed
                return [near[0]["source"].split(":", 1)[1]], want or iso(near[0])
    return [], None


def teams_and_countries():
    """{team: ISO code or None} for every club in the history and the live records (men's)."""
    out, pairs = {}, []
    HOME_DIV.clear()
    HOME_AT.clear()
    w = Path("data/work/matches.parquet")
    if w.exists():
        m = pd.read_parquet(w, columns=["division", "home", "away"])
        for div, h, a in m.itertuples(index=False):
            c = geo.DIVISION_COUNTRY.get(div)
            HOME_DIV.setdefault(h, div)
            for t in (h, a):
                out.setdefault(t, c)
    try:
        from astrofoot import live
        comp: dict[str, str | None] = {}
        for r in live.read_predictions():
            div = r["division"]
            if div not in comp:
                comp[div] = geo.DIVISION_COUNTRY.get(div) or competition_country(div)
            c = comp[div]                             # a domestic competition: both sides are from its country
            pairs.append((r["home"], r["away"]))
            if r.get("venue_lat") is not None and div not in live.MULTI_CLUB:
                HOME_AT.setdefault(r["home"], []).append((r["venue_lat"], r["venue_lon"]))
            out[r["away"]] = out.get(r["away"]) or c
            if not c and r.get("venue_lat") is not None and div not in live.MULTI_CLUB:
                c = nations.country_at(r["venue_lat"], r["venue_lon"])   # else the home side's ground
            out[r["home"]] = out.get(r["home"]) or c
    except Exception as e:  # noqa: BLE001
        print("live record unavailable:", e)
    # a club whose country is still unknown takes the country most of its opponents are from (2 or more, 2 in 3)
    from collections import Counter, defaultdict
    opp = defaultdict(list)
    for h, a in pairs:
        opp[h].append(a)
        opp[a].append(h)
    for t in [t for t, c in out.items() if not c and t in opp]:
        votes = Counter(out.get(o) for o in opp[t] if out.get(o) and not teamnames.nation(o))
        if votes:
            c, n = votes.most_common(1)[0]
            if n >= 2 and n * 3 >= sum(votes.values()) * 2:
                out[t] = c
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
    # a decision made under the current rules wins (a rejection included); then a name over none
    rank = lambda v: ((v or {}).get("v") or 0, bool((v or {}).get("short")))  # noqa: E731
    out = dict(theirs)
    for k, v in mine.items():
        if k not in out or rank(v) >= rank(out[k]):
            out[k] = v
    teamnames.FILE.write_text(json.dumps(out, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"merged: {sum(1 for v in out.values() if v.get('short'))} clubs named")


def club_search(base: str) -> list[str]:
    """Wikidata full-text search limited to association football clubs (P31 = Q476028), on the team's name words
    (initials like "T." left out): finds "Royal Excel Mouscron" for "Mouscron", "WSG Tirol" for "Tirol"."""
    words = [w for w in re.findall(r"[^\W\d_]{2,}|\d+", base.replace(".", ". ")) if len(w) > 1]
    if not words:
        return []
    q = " ".join(words) + " haswbstatement:" + "|".join(f"P31={c}" for c in sorted(FOOTBALL - {"Q6979593"}))
    d = get("https://www.wikidata.org/w/api.php?action=query&list=search&format=json&srnamespace=0&srlimit=8"
            "&srsearch=" + urllib.parse.quote(q))
    if d is None:
        print(f"  club search failed for {base!r}")
    hits = [h["title"] for h in ((d or {}).get("query") or {}).get("search", []) if h.get("title", "").startswith("Q")]
    print(f"  club search {base!r}: {len(hits)} hit(s)")
    return hits


def main():
    cache = json.loads(teamnames.FILE.read_text()) if teamnames.FILE.exists() else {}
    month = time.strftime("%Y-%m")
    teams = teams_and_countries()
    for k in [k for k in cache if teamnames.split(k)[1] and not k.startswith("W:")]:
        del cache[k]                                  # reserve / youth sides go through their club
    cand = {t: [cache[t]["qid"]] for t in teams if (cache.get(t) or {}).get("short") and cache[t].get("qid")
            and (cache[t].get("v") or 0) < NAMED_SINCE}   # redo with the current rules, same item
    unnamed = [t for t in teams if not (cache.get(t) or {}).get("short")
               and ((cache.get(t) or {}).get("v") or 0) < VERSION or
               (not (cache.get(t) or {}).get("short") and (cache.get(t) or {}).get("tried") != month)]
    todo = sorted(set(cand) | set(unnamed))
    print(f"{len(teams)} clubs; {len(todo)} to name ({len(cand)} redone, {len(unnamed)} not named yet)")
    for t in todo:
        if t in cand:
            better = table_candidates(t, teams.get(t))[0]
            if better and better[0] not in cand[t]:
                cand[t] = better                      # the table now points elsewhere (a stray alias before)
            continue
        c, country = table_candidates(t, teams.get(t))
        if c:
            cand[t] = c
            teams[t] = teams.get(t) or country     # the table's country confirms the item below
    rest = [t for t in todo if t not in cand]
    searched: set[str] = set()                        # candidates from the search: several may pass the checks
    print(f"searching Wikidata for {len(rest)} clubs the founding table does not match "
          f"({time.time() - START:.0f}s in)")
    search_start = time.time()
    for t in rest:
        if time.time() - search_start > BUDGET_S / 3:
            print("  search budget reached; the rest wait for the next run")
            break
        d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=5"
                "&search=" + urllib.parse.quote(teamnames.split(t)[0]))
        base = teamnames.split(t)[0]
        hits = [h["id"] for h in (d or {}).get("search", [])
                if similar(base, h.get("label") or "") or similar(t, h.get("label") or "")
                or (_words(base) and all(_abbrev_ok(w, _words(h.get("label") or "") | _words(" ".join(
                    (h.get("aliases") or []) + [h.get("match", {}).get("text") or ""]))) for w in _words(base)))]
        hits += club_search(base)                     # full-text, football clubs only ("Mouscron" -> the club)
        hits = list(dict.fromkeys(hits))
        time.sleep(0.15)
        if hits:
            cand[t] = hits
            searched.add(t)
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
        pick, why, passing = None, ["no Wikidata item found"], []
        for q in cand.get(t, []):
            e = ents.get(q) or {}
            if not set(claim_ids(e, "P31")) & FOOTBALL:
                why.append(f"{q}: not a football club")
                continue
            want = teams.get(t)
            have = {iso.get(c) for c in claim_ids(e, "P17")} - {None}
            if want and have and not same_country(want, have):
                why.append(f"{q}: in {sorted(have)}, not {want}")
                continue                              # a namesake in another country
            if not want and not have:
                at, ll = home_location(t), item_location(e)
                if not (at and ll and _km(at, ll) <= NEAR_KM):
                    why.append(f"{q}: no country to confirm with")
                    continue                          # nothing to confirm the match with
            if not names_agree(t, e, strict=t in searched):
                why.append(f"{q}: names differ")
                print(f"  rejected {t} -> {q} {((e.get('labels') or {}).get('en') or {}).get('value')}: names differ")
                continue
            if t not in searched:
                pick = (q, e)
                break
            passing.append((len(e.get("labels") or {}), q, e))
        if passing:
            passing.sort(key=lambda x: -x[0])         # prominence: the number of languages it is named in
            if len(passing) == 1 or passing[0][0] >= DOMINANCE * passing[1][0]:
                pick = passing[0][1:]
            elif (at := home_location(t)):
                # namesakes of similar standing: the one whose ground or seat is where the club plays
                near = [(n, q, e) for n, q, e in passing
                        if (ll := item_location(e)) and _km(at, ll) <= NEAR_KM]
                if len(near) == 1:
                    pick = near[0][1:]
            if not pick and len(passing) > 1:
                why.append("namesakes: " + ", ".join(f"{q} ({n})" for n, q, _ in passing[:3]))
        if not pick:
            cache[t] = {"tried": month, "why": "; ".join(why[1:] or why), "v": VERSION}
            continue
        q, e = pick
        legal, lang = official(e)
        short = short_name(e, lang)
        if short and not _agrees(t, short):
            # a label from another era, or a vandalised one ("Real Madrid" on Barracas Central's item): the first
            # Latin label, English first, that names the club as the team is known
            labels = e.get("labels") or {}
            for lang in ["en", lang or "", "es", "pt", "fr", "de", "it", "nl", *sorted(labels)]:
                v = tidy((labels.get(lang) or {}).get("value") or "")
                if v and is_latin(v) and _agrees(t, v):
                    short = v
                    break
        if legal and (sum(ch.isupper() for ch in legal) > 0.8 * sum(ch.isalpha() for ch in legal) > 8
                      or not (_agrees(t, legal) or _agrees(short, legal))):
            legal = None                              # a vandalised or unrelated official name: not trusted
        if not short:
            cache[t] = {"tried": month, "why": f"{q}: no Latin-script name", "v": VERSION}
            continue
        cache[t] = {"short": short, "legal": legal or short, "qid": q, "v": VERSION}
        found += 1
    teamnames.FILE.parent.mkdir(parents=True, exist_ok=True)
    teamnames.FILE.write_text(json.dumps(cache, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"found {found} official names; {sum(1 for v in cache.values() if v.get('short'))} clubs named in all")
    for t in sorted(t for t in todo if (cache.get(t) or {}).get("short")):
        print(f"  {t} -> {cache[t]['short']}  |  {cache[t]['legal']}")
    for t in sorted(t for t in todo if not (cache.get(t) or {}).get("short")):
        print(f"  not named: {t} ({teams.get(t)}): {(cache.get(t) or {}).get('why', 'lookup failed')}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--merge":
        merge(sys.argv[2])
    else:
        main()
