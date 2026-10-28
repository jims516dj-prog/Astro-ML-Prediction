"""Team -> home-venue coordinates.

Resolution order (each match records which one was used):
  1. stadium  - jokecamp/FootballData stadium GPS table (keyed on football-data.co.uk names)
  2. manual   - data/ref/team_city_overrides.csv (club -> city, hand-curated)
  3. city     - club name matched to a city of the league's country (dr5hn cities DB)
Teams that resolve to nothing get no coordinates; their matches are excluded from
angle/house features instead of being given a guessed location.
"""
from __future__ import annotations

import gzip
import re
import unicodedata
from functools import lru_cache

import pandas as pd

from .config import RAW, REF

DIVISION_COUNTRY = {
    "E0": "GB", "E1": "GB", "E2": "GB", "E3": "GB", "EC": "GB",
    "SC0": "GB", "SC1": "GB", "SC2": "GB", "SC3": "GB",
    "D1": "DE", "D2": "DE", "I1": "IT", "I2": "IT", "SP1": "ES", "SP2": "ES",
    "F1": "FR", "F2": "FR", "N1": "NL", "B1": "BE", "P1": "PT", "T1": "TR", "G1": "GR",
    "ARG": "AR", "AUT": "AT", "BRA": "BR", "CHN": "CN", "DEN": "DK", "FIN": "FI",
    "IRL": "IE", "JAP": "JP", "MEX": "MX", "NOR": "NO", "POL": "PL", "ROM": "RO",
    "RUS": "RU", "SUI": "CH", "SWE": "SE", "USA": "US",
}

# Words in club names that are never the city.
_STOP = {
    "fc", "cf", "ac", "as", "sc", "sv", "fk", "if", "bk", "ik", "afc", "cd", "ud", "rc", "sd",
    "real", "sporting", "sp", "ath", "atletico", "athletic", "united", "utd", "city", "town",
    "county", "rovers", "wanderers", "albion", "athletico", "dynamo", "dinamo", "spartak",
    "lokomotiv", "club", "de", "del", "la", "le", "les", "st", "rb", "vfb", "vfl", "tsg",
    "borussia", "eintracht", "fortuna", "hertha", "union", "olympique", "stade", "racing",
    "deportivo", "deportes", "independiente", "estudiantes", "atl", "csd", "ca", "nac", "psv",
    "fsv", "ssc", "us", "fbc", "calcio", "hellas", "inter", "fcsb", "cfr", "u", "1", "05",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


@lru_cache(maxsize=1)
def cities() -> pd.DataFrame:
    with gzip.open(RAW / "csv-cities.csv.gz", "rt", encoding="utf-8") as f:
        c = pd.read_csv(f, usecols=["name", "country_code", "latitude", "longitude",
                                    "population", "timezone"], low_memory=False)
    c["key"] = c["name"].map(norm)
    c["population"] = pd.to_numeric(c["population"], errors="coerce").fillna(0)
    # one row per (country, key): the most populous
    return (c.sort_values("population", ascending=False)
             .drop_duplicates(["country_code", "key"]))


@lru_cache(maxsize=1)
def stadiums() -> dict[str, tuple[float, float]]:
    s = pd.read_csv(RAW / "stadiums.csv", encoding="latin-1")
    return {str(r.FDCOUK).strip(): (float(r.Latitude), float(r.Longitude))
            for r in s.itertuples() if pd.notna(r.FDCOUK)}


@lru_cache(maxsize=1)
def overrides() -> dict[str, tuple[str, str]]:
    p = REF / "team_city_overrides.csv"
    if not p.exists():
        return {}
    o = pd.read_csv(p, comment="#")
    return {r.team: (r.country, r.city, r.lat, r.lon) for r in o.itertuples()}


def _city_lookup(country: str, name: str):
    c = cities()
    hit = c[(c.country_code == country) & (c.key == norm(name))]
    if len(hit):
        r = hit.iloc[0]
        return float(r.latitude), float(r.longitude)
    return None


def resolve(team: str, division: str):
    """Return (lat, lon, source) or None."""
    st = stadiums()
    if team in st:
        return (*st[team], "stadium")
    country = DIVISION_COUNTRY.get(division)
    ov = overrides()
    if team in ov:
        ctry, city, lat, lon = ov[team]
        ll = (float(lat), float(lon)) if pd.notna(lat) else _city_lookup(ctry, city)
        if ll:
            return (*ll, "manual")
    if country is None:
        return None
    ll = _city_lookup(country, team)
    if ll:
        return (*ll, "city")
    toks = [t for t in norm(team).split() if t not in _STOP and len(t) > 2]
    # try longest multi-token suffix first ("sp gijon" -> "gijon"; "west brom" stays unmatched)
    for i in range(len(toks)):
        ll = _city_lookup(country, " ".join(toks[i:]))
        if ll:
            return (*ll, "city")
    return None
