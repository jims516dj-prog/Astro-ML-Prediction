"""Official team names.

Shown on screen: for national teams the name registered with FIFA ("Korea Republic", "Czechia", "Congo DR",
"Türkiye"); for clubs the short official name they are registered under ("FC Bayern München", "Manchester United FC").
Used behind the scenes for name numerology: the full legal name of a club ("Fußball-Club Bayern München e. V."), and
FIFA's name for a national team.

The names the sources write ("Man United", "Bayern Munich") stay as they are internally: ratings, history, founding
dates and results are looked up by them. Club names come from Wikidata (official name P1448, labels), matched by
scripts/fetch_official_names.py and saved in data/ref/team_names.json; a club not matched yet keeps the source name."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .config import ROOT

FILE = ROOT / "data" / "ref" / "team_names.json"

# FIFA member associations, by ISO 3166 code (the four home nations by name), as FIFA writes them
FIFA = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria", "AS": "American Samoa", "AD": "Andorra", "AO": "Angola",
    "AI": "Anguilla", "AG": "Antigua and Barbuda", "AR": "Argentina", "AM": "Armenia", "AW": "Aruba", "AU": "Australia",
    "AT": "Austria", "AZ": "Azerbaijan", "BS": "Bahamas", "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados",
    "BY": "Belarus", "BE": "Belgium", "BZ": "Belize", "BJ": "Benin", "BM": "Bermuda", "BT": "Bhutan", "BO": "Bolivia",
    "BA": "Bosnia and Herzegovina", "BW": "Botswana", "BR": "Brazil", "VG": "British Virgin Islands",
    "BN": "Brunei Darussalam", "BG": "Bulgaria", "BF": "Burkina Faso", "BI": "Burundi", "CV": "Cabo Verde",
    "KH": "Cambodia", "CM": "Cameroon", "CA": "Canada", "KY": "Cayman Islands", "CF": "Central African Republic",
    "TD": "Chad", "CL": "Chile", "CN": "China PR", "TW": "Chinese Taipei", "CO": "Colombia", "KM": "Comoros",
    "CG": "Congo", "CD": "Congo DR", "CK": "Cook Islands", "CR": "Costa Rica", "CI": "Côte d'Ivoire", "HR": "Croatia",
    "CU": "Cuba", "CW": "Curaçao", "CY": "Cyprus", "CZ": "Czechia", "DK": "Denmark", "DJ": "Djibouti", "DM": "Dominica",
    "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt", "SV": "El Salvador", "GQ": "Equatorial Guinea",
    "ER": "Eritrea", "EE": "Estonia", "SZ": "Eswatini", "ET": "Ethiopia", "FO": "Faroe Islands", "FJ": "Fiji",
    "FI": "Finland", "FR": "France", "GA": "Gabon", "GM": "Gambia", "GE": "Georgia", "DE": "Germany", "GH": "Ghana",
    "GI": "Gibraltar", "GR": "Greece", "GD": "Grenada", "GU": "Guam", "GT": "Guatemala", "GN": "Guinea",
    "GW": "Guinea-Bissau", "GY": "Guyana", "HT": "Haiti", "HN": "Honduras", "HK": "Hong Kong, China", "HU": "Hungary",
    "IS": "Iceland", "IN": "India", "ID": "Indonesia", "IR": "IR Iran", "IQ": "Iraq", "IE": "Republic of Ireland",
    "IL": "Israel", "IT": "Italy", "JM": "Jamaica", "JP": "Japan", "JO": "Jordan", "KZ": "Kazakhstan", "KE": "Kenya",
    "KP": "Korea DPR", "KR": "Korea Republic", "XK": "Kosovo", "KW": "Kuwait", "KG": "Kyrgyz Republic", "LA": "Laos",
    "LV": "Latvia", "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya", "LI": "Liechtenstein",
    "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macau", "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia",
    "MV": "Maldives", "ML": "Mali", "MT": "Malta", "MR": "Mauritania", "MU": "Mauritius", "MX": "Mexico",
    "MD": "Moldova", "MN": "Mongolia", "ME": "Montenegro", "MS": "Montserrat", "MA": "Morocco", "MZ": "Mozambique",
    "MM": "Myanmar", "NA": "Namibia", "NP": "Nepal", "NL": "Netherlands", "NC": "New Caledonia", "NZ": "New Zealand",
    "NI": "Nicaragua", "NE": "Niger", "NG": "Nigeria", "MK": "North Macedonia", "NO": "Norway", "OM": "Oman",
    "PK": "Pakistan", "PS": "Palestine", "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico", "QA": "Qatar", "RO": "Romania",
    "RU": "Russia", "RW": "Rwanda", "WS": "Samoa", "SM": "San Marino", "ST": "São Tomé and Príncipe",
    "SA": "Saudi Arabia", "SN": "Senegal", "RS": "Serbia", "SC": "Seychelles", "SL": "Sierra Leone", "SG": "Singapore",
    "SK": "Slovakia", "SI": "Slovenia", "SB": "Solomon Islands", "SO": "Somalia", "ZA": "South Africa",
    "SS": "South Sudan", "ES": "Spain", "LK": "Sri Lanka", "KN": "St Kitts and Nevis", "LC": "St Lucia",
    "VC": "St Vincent and the Grenadines", "SD": "Sudan", "SR": "Suriname", "SE": "Sweden", "CH": "Switzerland",
    "SY": "Syria", "PF": "Tahiti", "TJ": "Tajikistan", "TZ": "Tanzania", "TH": "Thailand", "TL": "Timor-Leste",
    "TG": "Togo", "TO": "Tonga", "TT": "Trinidad and Tobago", "TN": "Tunisia", "TR": "Türkiye", "TM": "Turkmenistan",
    "TC": "Turks and Caicos Islands", "UG": "Uganda", "UA": "Ukraine", "AE": "United Arab Emirates", "UY": "Uruguay",
    "VI": "US Virgin Islands", "US": "USA", "UZ": "Uzbekistan", "VU": "Vanuatu", "VE": "Venezuela", "VN": "Vietnam",
    "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe",
    "GB-england": "England", "GB-scotland": "Scotland", "GB-wales": "Wales", "GB-northern ireland": "Northern Ireland",
}
# not FIFA members (CONCACAF or regional teams): their own names
NON_FIFA = {"BQ": "Bonaire", "GF": "French Guiana", "GP": "Guadeloupe", "MQ": "Martinique", "SX": "Sint Maarten",
            "MF": "Saint-Martin", "MC": "Monaco"}

_SUFFIX = re.compile(r"(?i)\s+((?:U-?|Under[- ]?|Sub-?)\d{2}|Reserves?|Res\.?|II|B|W|Women|Ladies|\(W\))$")


@lru_cache(maxsize=1)
def _clubs() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def reload() -> None:
    _clubs.cache_clear()


def split(name: str) -> tuple[str, str]:
    """("South Korea", " U21") from "South Korea U21": the team and its age / level suffixes, as written."""
    base, suffix = (name or "").strip(), ""
    while (m := _SUFFIX.search(base)):
        suffix = m.group(0) + suffix
        base = base[:m.start()].rstrip()
    return base, suffix


def _suffix(s: str) -> str:
    s = re.sub(r"(?i)\b(?:U-?|Under[- ]?|Sub-?)(\d{2})\b", r"U\1", s)
    s = s.strip()
    return f" {s}" if s else ""


def nation(name: str) -> str | None:
    """FIFA's name for a national team (with its age / level suffix), or None for a club."""
    from .live import team_identity
    base, suffix = split(name)
    code = team_identity(base)[0]
    if not code:
        return None
    fifa = FIFA.get(code) or NON_FIFA.get(code)
    return f"{fifa}{_suffix(suffix)}" if fifa else None


def display(name: str) -> str:
    """The name to show: FIFA's for a national team, the club's short official name, else the name as given."""
    if not isinstance(name, str) or not name:
        return name
    n = nation(name)
    if n:
        return n
    c = _clubs().get(name)
    if c and c.get("short"):
        return c["short"]
    base, suffix = split(name)
    c = _clubs().get(base) if suffix else None
    if c and c.get("short"):
        return f"{c['short']}{_suffix(suffix)}"
    return name


def legal(name: str, women: bool = False) -> str | None:
    """The full legal name used for name numerology (None when not known: the caller keeps its own)."""
    if not isinstance(name, str) or not name:
        return None
    n = nation(name)
    if n:
        return split(n)[0]
    for key in ((f"W:{name}",) if women else (name,)):     # a women's team never takes the men's club's name
        c = _clubs().get(key)
        if c and c.get("legal"):
            return c["legal"]
    base, suffix = split(name)
    if suffix and not women:
        c = _clubs().get(base)
        if c and c.get("legal"):
            return c["legal"]
    return None
