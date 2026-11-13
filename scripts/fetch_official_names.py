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
VERSION = 19          # unnamed clubs decided under an older version of the rules are tried again
NAMED_SINCE = 13      # named clubs are redone only when named under an older version than this
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
    plain = re.sub(r"\b[A-Z]&[A-Z]\b", " ", plain)  # "R&F" is a name, not two initials
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


def _vowel_variant(a: str, b: str) -> bool:
    """The two spellings differ by one vowel only: swapped, added or dropped."""
    v = set("aeiouy")
    if len(a) == len(b):
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        return len(diff) == 1 and diff[0][0] in v and diff[0][1] in v
    if abs(len(a) - len(b)) != 1:
        return False
    s, l = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(l)):
        if l[:i] + l[i + 1:] == s:
            return l[i] in v
    return False


def _abbrev_ok(word: str, theirs: set[str]) -> bool:
    """"rvs" ~ "rovers", "atl" ~ "atletico", "dynamo" ~ "dinamo", "go" ~ "goianiense": a prefix, a close spelling or
    an in-order contraction (same first letter)."""
    import difflib
    for t in theirs:
        if t.startswith(word) or (len(t) >= 3 and word.startswith(t)):
            return True
        if len(word) >= 4 and word[0] == t[0] and _vowel_variant(word, t):
            return True                               # "dynamo" ~ "dinamo", "nykoebing" ~ "nykobing"; not "ceuta" ~ "celta"
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


PLAYED: dict[str, list] = {}      # team -> [first year, last year] it played in our records


def _played(team, kickoff) -> None:
    y = str(kickoff or "")[:4]
    if not y.isdigit():
        return
    y = int(y)
    span = PLAYED.setdefault(teamnames.split(team)[0], [y, y])
    span[0], span[1] = min(span[0], y), max(span[1], y)


def _year(e, prop):
    for c in (e.get("claims") or {}).get(prop, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        t = str(v.get("time") or "")
        if len(t) > 5 and t[1:5].isdigit():
            return int(t[1:5])
    return None


def item_tokens(e) -> set[str]:
    out = set()
    for v in (e.get("labels") or {}).values():
        out |= _tokens(v.get("value"))
    for vs in (e.get("aliases") or {}).values():
        for v in vs:
            out |= _tokens(v.get("value"))
    return out


def lifetime_ok(team: str, e) -> bool:
    """The club existed while the team played: not founded after its last game in our records, nor dissolved
    before its first (a year's slack): "Volga N. Novgorod" (2012-2014) is not FC Nizhny Novgorod (founded 2015).
    The test is lenient because one name in the records can span a club and its refounding."""
    span = PLAYED.get(teamnames.split(team)[0])
    if not span:
        return True
    born, gone = _year(e, "P571"), _year(e, "P576")
    return not ((born and born > span[1]) or (gone and gone < span[0] - 1))


HOME_AT: dict[str, list] = {}     # team -> home-game venues in the live record
HOME_DIV: dict[str, str] = {}     # team -> a division it hosted games in (history)
NEAR_KM = 40
FAR_KM = 150         # a spelling-only match based further than this from the club's home is not taken


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
        if got and got[2] != "city":                  # stadium or curated city, not one read from the name
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
    got = _table_candidates(team, want)
    words = teamnames.split(team)[0].split()
    if not got[0] and want == "BR" and len(words) > 1 and words[-1].lower() in BR_STATES:
        got = _table_candidates(" ".join(words[:-1]), want)   # "Red Bull Bragantino SP" -> the club itself
    return got


def _table_candidates(team: str, want: str | None) -> tuple[list[str], str | None]:
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
    found = foundings.search(base, limit=12)
    if expand(base) != base:
        found += foundings.search(expand(base), limit=12)   # "Ind. Rivadavia" -> "Independiente Rivadavia"
    for x in found + namesakes(mine, want):
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
    if at:
        dist = lambda x: _km(at, (x["lat"], x["lon"])) if x.get("lat") is not None else None  # noqa: E731
        near = [x for x in pool if (d := dist(x)) is not None and d <= NEAR_KM]
        if near:
            pool = near                               # where the club plays decides first (Central Córdoba of
            # Santiago del Estero, not Instituto Atlético Central Córdoba of Córdoba)
        else:
            pool = [x for x in pool if x["match"] != "close" or (d := dist(x)) is None or d <= FAR_KM]
        if not pool:
            return [], None
    exact = [x for x in pool if mine and mine <= set().union(*(_tokens(n) for n in _row_names(x["source"])))]
    if exact and not initialism:
        pool = exact                                  # "Stirling" is Stirling Albion, not East Stirlingshire
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
    PLAYED.clear()
    HOME_DIV.clear()
    HOME_AT.clear()
    w = Path("data/work/matches.parquet")
    if w.exists():
        m = pd.read_parquet(w, columns=["division", "home", "away", "kickoff_utc"])
        for div, h, a, ko in m.itertuples(index=False):
            c = geo.DIVISION_COUNTRY.get(div)
            HOME_DIV.setdefault(h, div)
            for t in (h, a):
                out.setdefault(t, c)
                _played(t, ko)
    try:
        from astrofoot import live
        comp: dict[str, str | None] = {}
        for r in live.read_predictions():
            div = r["division"]
            if div not in comp:
                comp[div] = geo.DIVISION_COUNTRY.get(div) or competition_country(div)
            c = comp[div]                             # a domestic competition: both sides are from its country
            pairs.append((r["home"], r["away"]))
            for side in (r["home"], r["away"]):
                _played(side, r.get("kickoff_utc"))
            if (r.get("venue_lat") is not None and div not in live.MULTI_CLUB
                    and r.get("venue_source") != "city"):  # a city guessed from the name proves nothing
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


ABBREV = {"ind": "Independiente", "atl": "Atlético", "dep": "Deportivo", "univ": "Universidad", "din": "Dinamo",
          "utd": "United", "rvs": "Rovers", "jrs": "Juniors", "sp": "Sporting", "ath": "Athletic", "gim": "Gimnasia",
          "est": "Estudiantes", "spt": "Sporting", "wed": "Wednesday", "weds": "Wednesday"}
BR_STATES = {"ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe",
             "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"}


def expand(base: str) -> str:
    """Source abbreviations written out for searching: "Ind. Rivadavia" -> "Independiente Rivadavia"."""
    return " ".join(ABBREV.get(w.lower().rstrip("."), w) if w.endswith(".") or w.lower() in ("utd", "rvs", "jrs")
                    else w for w in base.split())


GENERIC_CLUB = {"Q847017"}   # "sports club": football only when its sport (P641) says so


CURATED_FILE = Path("data/ref/team_names_curated.csv")


def curated() -> dict[str, str]:
    """{team: article(s) | Q id | =Other team} from the hand-checked list."""
    if not CURATED_FILE.exists():
        return {}
    c = pd.read_csv(CURATED_FILE, comment="#", dtype=str, keep_default_na=False)
    return {r.team.strip(): r.article.strip() for r in c.itertuples() if r.team.strip() and r.article.strip()}


def wiki_items(titles: list[str]) -> dict[str, str]:
    """{English Wikipedia title: Wikidata id}: through Wikidata's sitelinks (the API the rest of this script uses,
    which answers reliably), then Wikipedia itself for titles that are redirects; one title per Wikipedia request,
    so a redirect can never be credited to another title."""
    out = {}
    norm = lambda x: x.replace("_", " ").strip()  # noqa: E731
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        d = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&props=sitelinks"
                "&sitefilter=enwiki&titles=" + urllib.parse.quote("|".join(batch)))
        for q, e in ((d or {}).get("entities") or {}).items():
            title = (((e.get("sitelinks") or {}).get("enwiki")) or {}).get("title")
            if q.startswith("Q") and title:
                for t in batch:
                    if norm(t) == norm(title):
                        out[t] = q
        time.sleep(0.5)
    for title in [t for t in titles if t not in out]:      # redirects: ask Wikipedia
        url = ("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&ppprop=wikibase_item"
               "&redirects=1&titles=" + urllib.parse.quote(title))
        d = get(url)
        if d is None:
            time.sleep(20)
            d = get(url, tries=3)
        pages = list((((d or {}).get("query") or {}).get("pages") or {}).values())
        item = (pages[0].get("pageprops") or {}).get("wikibase_item") if len(pages) == 1 else None
        if item:
            out[title] = item
        time.sleep(1.5)
    return out


GENERIC_CLUB = {"Q847017"}   # "sports club": football only when its sport (P641) says so


CURATED_FILE = Path("data/ref/team_names_curated.csv")


def curated() -> dict[str, str]:
    """{team: article(s) | Q id | =Other team} from the hand-checked list."""
    if not CURATED_FILE.exists():
        return {}
    c = pd.read_csv(CURATED_FILE, comment="#", dtype=str, keep_default_na=False)
    return {r.team.strip(): r.article.strip() for r in c.itertuples() if r.team.strip() and r.article.strip()}


def wiki_items(titles: list[str]) -> dict[str, str]:
    """{English Wikipedia title: Wikidata id}, redirects followed; one title per request, so a redirect can never
    be credited to another title."""
    out = {}
    for title in titles:
        url = ("https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageprops&ppprop=wikibase_item"
               "&redirects=1&titles=" + urllib.parse.quote(title))
        d = get(url)
        if d is None:                                 # turned away: wait and try once more
            time.sleep(20)
            d = get(url, tries=3)
        pages = list((((d or {}).get("query") or {}).get("pages") or {}).values())
        item = (pages[0].get("pageprops") or {}).get("wikibase_item") if len(pages) == 1 else None
        if item:
            out[title] = item
        time.sleep(1.5)
    return out


WOMEN_CLUB = {"Q51481377", "Q28140340"}   # women's association football club


def club_search(base: str) -> list[str]:
    """Wikidata full-text search limited to association football clubs (P31 = Q476028), on the team's name words
    (initials like "T." left out): finds "Royal Excel Mouscron" for "Mouscron", "WSG Tirol" for "Tirol"."""
    words = [w for w in re.findall(r"[^\W\d_]{2,}|\d+", expand(base).replace(".", ". ")) if len(w) > 1]
    if not words:
        return []
    q = " ".join(words) + " haswbstatement:" + "|".join(f"P31={c}" for c in sorted(FOOTBALL - {"Q6979593"}))
    url = ("https://www.wikidata.org/w/api.php?action=query&list=search&format=json&srnamespace=0&srlimit=20"
           "&srsearch=" + urllib.parse.quote(q))
    d = get(url)
    for wait in (15, 45):                             # rate limited: wait and try again
        if d is not None:
            break
        time.sleep(wait)
        d = get(url, tries=3)
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
    picked = curated()
    hand: set[str] = set()                            # clubs identified by hand: their item is taken as given
    held: set[str] = set()                            # identified by hand, but the look-up failed: left alone
    titles = sorted({a for v in picked.values() if not v.startswith(("=", "Q")) for a in v.split("|")})
    items = wiki_items(titles) if titles else {}
    for t, v in picked.items():
        if t not in teams:
            continue
        if v.startswith("="):
            continue                                  # copied from the other team at the end
        qs = [v] if re.fullmatch(r"Q\d+", v) else list(dict.fromkeys(items[a] for a in v.split("|") if a in items))
        if not qs:
            print(f"  curated {t}: no Wikidata item for {v!r}; its entry is kept as it is")
            held.add(t)
            continue
        if (cache.get(t) or {}).get("qid") not in qs or (cache.get(t) or {}).get("v") != VERSION:
            cand[t] = qs                              # tried in order: the first that existed when the team played
            hand.add(t)
    todo = sorted((set(todo) | hand) - held)
    for t in held:
        cand.pop(t, None)
    print(f"{len(teams)} clubs; {len(todo)} to name ({len(cand)} redone, {len(unnamed)} not named yet, "
          f"{len(hand)} identified by hand)")
    for t in todo:
        if t in hand:
            continue                                  # the hand-checked item alone
        if t in cand:
            better = table_candidates(t, teams.get(t))[0]
            if better and better[0] not in cand[t]:
                cand[t] = cand[t] + better            # the club keeps its item unless that fails the checks
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
    def search(t):
        base = teamnames.split(t)[0]
        d = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=5"
                "&search=" + urllib.parse.quote(base))
        hits = [h["id"] for h in (d or {}).get("search", [])
                if similar(base, h.get("label") or "") or similar(t, h.get("label") or "")
                or (_words(base) and all(_abbrev_ok(w, _words(h.get("label") or "") | _words(" ".join(
                    (h.get("aliases") or []) + [h.get("match", {}).get("text") or ""]))) for w in _words(base)))]
        hits += club_search(base)                     # full-text, football clubs only ("Mouscron" -> the club)
        words = base.split()
        if teams.get(t) == "BR" and len(words) > 1 and words[-1].lower() in BR_STATES:
            hits += club_search(" ".join(words[:-1]))  # "Red Bull Bragantino SP": the state is not in the name
        time.sleep(1.0)                               # the API's fair use: searches were being turned away
        return list(dict.fromkeys(hits))

    for t in rest:
        if time.time() - search_start > BUDGET_S / 3:
            print("  search budget reached; the rest wait for the next run")
            break
        hits = search(t)
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
    def decide(t):
        """Names the club from its candidates; True when named, False when not, None when the lookup failed."""
        if cand.get(t) and not any(q in ents for q in cand[t]):
            return None                               # the lookup failed: try again next run, keep the entry
        pick, why, passing = None, ["no Wikidata item found"], []
        for q in cand.get(t, []):
            e = ents.get(q) or {}
            if t in hand:
                kinds = set(claim_ids(e, "P31")) & (FOOTBALL | WOMEN_CLUB)
                if not kinds or (kinds <= GENERIC_CLUB and "Q2736" not in claim_ids(e, "P641")):
                    why.append(f"{q}: not a football club")
                    continue                          # a redirect to a station or a league is never taken
                if not lifetime_ok(t, e):
                    why.append(f"{q}: founded {_year(e, 'P571')} / dissolved {_year(e, 'P576')}, "
                               f"but the team played {PLAYED.get(teamnames.split(t)[0])}")
                    continue
                pick = (q, e)                         # identified by hand: only its lifetime is checked
                break
            en = ((e.get("labels") or {}).get("en") or {}).get("value") or ""
            if RESERVE_ITEM.search(en) and not RESERVE_ITEM.search(teamnames.split(t)[0]):
                why.append(f"{q}: a reserve, youth or women's side ({en})")
                continue                              # "América de Cali B" for América de Cali
            kinds = set(claim_ids(e, "P31")) & FOOTBALL
            if not kinds:
                why.append(f"{q}: not a football club")
                continue
            if kinds <= GENERIC_CLUB and "Q2736" not in claim_ids(e, "P641"):
                why.append(f"{q}: a sports club, not shown to play football")
                continue                              # "Hornchurch Cricket Club"
            want = teams.get(t)
            have = {iso.get(c) for c in claim_ids(e, "P17")} - {None}
            if want and have and not same_country(want, have):
                why.append(f"{q}: in {sorted(have)}, not {want}")
                continue                              # a namesake in another country
            if want and not have and t in searched:
                at, ll = home_location(t), item_location(e)
                if not (at and ll and _km(at, ll) <= NEAR_KM):
                    why.append(f"{q}: no country to confirm with")
                    continue                          # "Mega Sport" (Egypt) is not Aris Mega Revma (Greece)
            if not want and not have:
                at, ll = home_location(t), item_location(e)
                if not (at and ll and _km(at, ll) <= NEAR_KM):
                    why.append(f"{q}: no country to confirm with")
                    continue                          # nothing to confirm the match with
            if t in searched and (at := home_location(t)) and (ll := item_location(e)) and _km(at, ll) > FAR_KM:
                why.append(f"{q}: based {_km(at, ll):.0f} km from where the team plays")
                continue                              # "Kuban" (Krasnodar) is not FC Kuban Holding (Pavlovskaya)
            if not lifetime_ok(t, e):
                why.append(f"{q}: founded {_year(e, 'P571')} / dissolved {_year(e, 'P576')}, "
                           f"but the team played {PLAYED.get(teamnames.split(t)[0])}")
                continue
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
            if not pick:
                # namesakes of similar standing: the one whose own names carry every word of the team's name
                # ("Tirol" -> WSG Tirol, not Wacker Innsbruck; "Guangzhou R&F" -> Guangzhou City, not Guangzhou FC)
                mine = _tokens(teamnames.split(t)[0])
                full = [(n, q, e) for n, q, e in passing if mine and mine <= item_tokens(e)]
                if len(full) == 1:
                    pick = full[0][1:]
            if not pick and (at := home_location(t)):
                # namesakes of similar standing: the one whose ground or seat is where the club plays
                near = [(n, q, e) for n, q, e in passing
                        if (ll := item_location(e)) and _km(at, ll) <= NEAR_KM]
                if len(near) == 1:
                    pick = near[0][1:]
            if not pick and len(passing) > 1:
                why.append("namesakes: " + ", ".join(f"{q} ({n})" for n, q, _ in passing[:3]))
        if not pick:
            cache[t] = {"tried": month, "why": "; ".join(why[1:] or why), "v": VERSION}
            return False
        q, e = pick
        legal, lang = official(e)
        short = short_name(e, lang)
        if short and t not in hand and not _agrees(t, short):
            # a label from another era, or a vandalised one ("Real Madrid" on Barracas Central's item): the first
            # Latin label, English first, that names the club as the team is known
            labels = e.get("labels") or {}
            for lang in ["en", lang or "", "es", "pt", "fr", "de", "it", "nl", *sorted(labels)]:
                v = tidy((labels.get(lang) or {}).get("value") or "")
                if v and is_latin(v) and _agrees(t, v):
                    short = v
                    break
        if t in searched and short and not _agrees(t, short):
            cache[t] = {"tried": month, "why": f"{q}: none of its names is the team's ({short})", "v": VERSION}
            return False                              # "Padova" only as an alias of Vigontina San Paolo FC
        if legal and (sum(ch.isupper() for ch in legal) > 0.8 * sum(ch.isalpha() for ch in legal) > 8
                      or not (_agrees(t, legal) or _agrees(short, legal))):
            legal = None                              # a vandalised or unrelated official name: not trusted
        if not short:
            cache[t] = {"tried": month, "why": f"{q}: no Latin-script name", "v": VERSION}
            return False
        cache[t] = {"short": short, "legal": legal or short, "qid": q, "v": VERSION}
        return True

    found = sum(1 for t in todo if decide(t))
    # a club whose table item was turned down (a predecessor, a namesake abroad) is searched for in Wikidata
    retry = [t for t in todo if t not in searched and not (cache.get(t) or {}).get("short")
             and cand.get(t) and any(q in ents for q in cand[t])]
    if retry:
        print(f"searching Wikidata again for {len(retry)} clubs whose table match was turned down")
        for t in retry:
            if time.time() - search_start > BUDGET_S * 2 / 3:
                break
            hits = [q for q in search(t) if q not in cand[t]]
            if hits:
                cand[t] = hits
                searched.add(t)
        more = sorted({q for t in retry for q in cand.get(t, [])} - set(ents))
        ents.update(entities(more))
        new_c = sorted({c for q in more for c in claim_ids(ents.get(q) or {}, "P17") if c} - set(iso))
        for q, e in entities(new_c, labels=False).items():
            for c in (e.get("claims") or {}).get("P297", []):
                iso[q] = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        found += sum(1 for t in retry if t in searched and decide(t))
    for t, v in picked.items():
        if t in teams and v.startswith("=") and (cache.get(v[1:]) or {}).get("short"):
            cache[t] = {**cache[v[1:]], "v": VERSION}  # the same club under another name
    for t in sorted(hand):
        c = cache.get(t) or {}
        print(f"  curated {t} -> {c.get('short') or 'not named: ' + str(c.get('why'))}")
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
