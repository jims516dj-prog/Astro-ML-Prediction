"""National teams: country codes and a 'which country is this point in' check, so a national team's ground is
never placed in another country (map searches sometimes return a namesake stadium abroad)."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from . import geo

NATIONS = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "American Samoa": "AS", "Andorra": "AD", "Angola": "AO",
    "Anguilla": "AI", "Antigua and Barbuda": "AG", "Argentina": "AR", "Armenia": "AM", "Aruba": "AW", "Australia": "AU",
    "Austria": "AT", "Azerbaijan": "AZ", "Bahamas": "BS", "Bahrain": "BH", "Bangladesh": "BD", "Barbados": "BB",
    "Belarus": "BY", "Belgium": "BE", "Belize": "BZ", "Benin": "BJ", "Bermuda": "BM", "Bhutan": "BT", "Bolivia": "BO",
    "Bonaire": "BQ", "Bosnia and Herzegovina": "BA", "Bosnia-Herzegovina": "BA", "Botswana": "BW", "Brazil": "BR",
    "British Virgin Islands": "VG", "Brunei": "BN", "Brunei Darussalam": "BN", "Bulgaria": "BG", "Burkina Faso": "BF",
    "Burundi": "BI", "Cambodia": "KH", "Cameroon": "CM", "Canada": "CA", "Cape Verde": "CV", "Cabo Verde": "CV",
    "Cape Verde Islands": "CV", "Cayman Islands": "KY", "Central African Republic": "CF", "Chad": "TD", "Chile": "CL",
    "China": "CN", "China PR": "CN", "Chinese Taipei": "TW", "Colombia": "CO", "Comoros": "KM", "Congo": "CG",
    "Congo DR": "CD", "DR Congo": "CD", "Democratic Republic of the Congo": "CD", "Cook Islands": "CK", "Costa Rica": "CR",
    "Croatia": "HR", "Cuba": "CU", "Curaçao": "CW", "Curacao": "CW", "Cyprus": "CY", "Czechia": "CZ", "Czech Republic": "CZ",
    "Denmark": "DK", "Djibouti": "DJ", "Dominica": "DM", "Dominican Republic": "DO", "Ecuador": "EC", "Egypt": "EG",
    "El Salvador": "SV", "England": "GB", "Equatorial Guinea": "GQ", "Eritrea": "ER", "Estonia": "EE", "Eswatini": "SZ",
    "Swaziland": "SZ", "Ethiopia": "ET", "Faroe Islands": "FO", "Fiji": "FJ", "Finland": "FI", "France": "FR",
    "French Guiana": "GF", "Gabon": "GA", "Gambia": "GM", "The Gambia": "GM", "Georgia": "GE", "Germany": "DE",
    "Ghana": "GH", "Gibraltar": "GI", "Greece": "GR", "Grenada": "GD", "Guadeloupe": "GP", "Guam": "GU", "Guatemala": "GT",
    "Guinea": "GN", "Guinea-Bissau": "GW", "Guyana": "GY", "Haiti": "HT", "Honduras": "HN", "Hong Kong": "HK",
    "Hong Kong, China": "HK", "Hungary": "HU", "Iceland": "IS", "India": "IN", "Indonesia": "ID", "Iran": "IR",
    "IR Iran": "IR", "Iraq": "IQ", "Ireland": "IE", "Republic of Ireland": "IE", "Israel": "IL", "Italy": "IT",
    "Ivory Coast": "CI", "Côte d'Ivoire": "CI", "Cote d'Ivoire": "CI", "Jamaica": "JM", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kosovo": "XK", "Kuwait": "KW", "Kyrgyzstan": "KG", "Kyrgyz Republic": "KG",
    "Laos": "LA", "Latvia": "LV", "Lebanon": "LB", "Lesotho": "LS", "Liberia": "LR", "Libya": "LY", "Liechtenstein": "LI",
    "Lithuania": "LT", "Luxembourg": "LU", "Macau": "MO", "Macao": "MO", "Madagascar": "MG", "Malawi": "MW",
    "Malaysia": "MY", "Maldives": "MV", "Mali": "ML", "Malta": "MT", "Martinique": "MQ", "Mauritania": "MR",
    "Mauritius": "MU", "Mexico": "MX", "Moldova": "MD", "Monaco": "MC", "Mongolia": "MN", "Montenegro": "ME",
    "Montserrat": "MS", "Morocco": "MA", "Mozambique": "MZ", "Myanmar": "MM", "Namibia": "NA", "Nepal": "NP",
    "Netherlands": "NL", "New Caledonia": "NC", "New Zealand": "NZ", "Nicaragua": "NI", "Niger": "NE", "Nigeria": "NG",
    "North Korea": "KP", "Korea DPR": "KP", "North Macedonia": "MK", "Northern Ireland": "GB", "Norway": "NO",
    "Oman": "OM", "Pakistan": "PK", "Palestine": "PS", "Panama": "PA", "Papua New Guinea": "PG", "Paraguay": "PY",
    "Peru": "PE", "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Puerto Rico": "PR", "Qatar": "QA",
    "Romania": "RO", "Russia": "RU", "Rwanda": "RW", "Saint Kitts and Nevis": "KN", "St. Kitts and Nevis": "KN",
    "St Kitts and Nevis": "KN", "Saint Lucia": "LC", "St. Lucia": "LC", "St Lucia": "LC", "Saint Martin": "MF",
    "St. Martin": "MF", "Saint Vincent and the Grenadines": "VC", "St. Vincent and the Grenadines": "VC",
    "St Vincent and the Grenadines": "VC", "St. Vincent / Grenadines": "VC", "Samoa": "WS", "San Marino": "SM",
    "São Tomé and Príncipe": "ST", "Sao Tome and Principe": "ST", "Saudi Arabia": "SA", "Scotland": "GB",
    "Senegal": "SN", "Serbia": "RS", "Seychelles": "SC", "Sierra Leone": "SL", "Singapore": "SG", "Sint Maarten": "SX",
    "Slovakia": "SK", "Slovenia": "SI", "Solomon Islands": "SB", "Somalia": "SO", "South Africa": "ZA",
    "South Korea": "KR", "Korea Republic": "KR", "South Sudan": "SS", "Spain": "ES", "Sri Lanka": "LK", "Sudan": "SD",
    "Suriname": "SR", "Sweden": "SE", "Switzerland": "CH", "Syria": "SY", "Tahiti": "PF", "Tajikistan": "TJ",
    "Tanzania": "TZ", "Thailand": "TH", "Timor-Leste": "TL", "East Timor": "TL", "Togo": "TG", "Tonga": "TO",
    "Trinidad and Tobago": "TT", "Tunisia": "TN", "Turkey": "TR", "Türkiye": "TR", "Turkmenistan": "TM",
    "Turks and Caicos Islands": "TC", "Uganda": "UG", "Ukraine": "UA", "United Arab Emirates": "AE", "UAE": "AE",
    "United States": "US", "USA": "US", "Uruguay": "UY", "US Virgin Islands": "VI", "U.S. Virgin Islands": "VI",
    "Uzbekistan": "UZ", "Vanuatu": "VU", "Venezuela": "VE", "Vietnam": "VN", "Wales": "GB", "Yemen": "YE",
    "Zambia": "ZM", "Zimbabwe": "ZW",
}
_YOUTH = re.compile(r"\s+(U-?\d{2}|Under[- ]?\d{2}|Sub-?\d{2}|Olympic)$", re.I)


def code_of(team: str) -> str | None:
    """ISO code when `team` is a national team ("Grenada", "England U21"), else None."""
    return NATIONS.get(_YOUTH.sub("", (team or "").strip()))


@lru_cache(maxsize=1)
def _index():
    c = geo.cities()
    return (np.radians(c.latitude.to_numpy(float)), np.radians(c.longitude.to_numpy(float)),
            c.country_code.to_numpy())


def country_at(lat: float, lon: float) -> str | None:
    """Country code of the nearest city in the cities table (None if the table is missing)."""
    try:
        la, lo, cc = _index()
    except Exception:  # noqa: BLE001
        return None
    p, q = np.radians(float(lat)), np.radians(float(lon))
    d = np.sin((la - p) / 2) ** 2 + np.cos(p) * np.cos(la) * np.sin((lo - q) / 2) ** 2
    return str(cc[int(np.argmin(d))])


# territories that share a football association with, or sit inside, another code in the cities table
SAME = {"GB": {"GB", "IM", "JE", "GG"}, "BQ": {"BQ", "CW", "AW"}, "CW": {"CW", "BQ", "AW"}, "AW": {"AW", "CW", "BQ"},
        "XK": {"XK", "RS"}, "AD": {"AD", "ES", "FR"}, "SM": {"SM", "IT"}, "VA": {"VA", "IT"}, "LI": {"LI", "CH", "AT"},
        "MC": {"MC", "FR"}, "GI": {"GI", "ES"}}


def in_country(lat: float, lon: float, code: str) -> bool:
    at = country_at(lat, lon)
    return at is None or at == code or at in SAME.get(code, set())


# the cities table also lists some regions with their population; those are never the answer
REGION = re.compile(r"(?i)\b(?:metropolitan|province|county|region|district|prefecture|upper|lower|oblast|parganas|"
                    r"governorate)\b|shire$|^(?:swabia|franconia|bavaria)$")
# home nations share the code GB: their own main city
HOME_NATION = {"England": "London", "Scotland": "Glasgow", "Wales": "Cardiff", "Northern Ireland": "Belfast"}


def largest_city(code: str, city: str | None = None):
    """(lat, lon, city name) of the most populous city in the cities table for an ISO code, or None."""
    try:
        c = geo.cities()
    except Exception:  # noqa: BLE001
        return None
    rows = c[c.country_code == code]
    if city:
        rows = rows[rows["name"] == city]
    rows = rows[~rows["name"].str.contains(REGION, na=False)].sort_values("population", ascending=False)
    if not len(rows):
        return None
    r = rows.iloc[0]
    return float(r.latitude), float(r.longitude), str(r["name"])
