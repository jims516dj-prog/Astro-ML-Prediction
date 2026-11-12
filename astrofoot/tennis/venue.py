"""The venue's timezone and local match day. ESPN gives venues as "City, Country" (sometimes only the country);
the city's timezone comes from the cities table (dr5hn). The day's chart uses the calendar day at the venue."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .. import geo

EXTRA_CODES = {"Great Britain": "GB", "New Zealand": "NZ", "Monaco": "MC", "Kazakhstan": "KZ", "Slovenia": "SI",
               "Thailand": "TH", "Singapore": "SG", "Tunisia": "TN", "Philippines": "PH", "Angola": "AO", "Hong Kong": "HK",
               "Bulgaria": "BG", "Slovakia": "SK", "Estonia": "EE", "Latvia": "LV", "Lithuania": "LT", "Georgia": "GE",
               "Uzbekistan": "UZ", "Indonesia": "ID", "Malaysia": "MY", "Taiwan": "TW", "Chinese Taipei": "TW",
               "Vietnam": "VN", "Luxembourg": "LU", "Puerto Rico": "PR", "Dominican Republic": "DO", "Kenya": "KE",
               "Bosnia and Herzegovina": "BA", "Bosnia-Herzegovina": "BA", "Montenegro": "ME", "North Macedonia": "MK",
               "Iceland": "IS", "Malta": "MT", "Belarus": "BY", "Moldova": "MD", "Armenia": "AM", "Azerbaijan": "AZ",
               "Pakistan": "PK", "Sri Lanka": "LK", "Bahrain": "BH", "Kuwait": "KW", "Oman": "OM", "Jordan": "JO",
               "Lebanon": "LB", "Algeria": "DZ", "Ivory Coast": "CI", "Senegal": "SN", "Zimbabwe": "ZW", "Barbados": "BB",
               "Bahamas": "BS", "Trinidad and Tobago": "TT", "Korea": "KR", "Republic of Korea": "KR", "Russia": "RU",
               "Great Britain ": "GB", "UK": "GB", "U.S.A.": "US", "Czech Republic": "CZ", "Holland": "NL",
               "The Netherlands": "NL", "UAE": "AE", "Columbia": "CO", "China PR": "CN", "Korea Republic": "KR"}
CITY_ALIAS = {"washington dc": "washington", "st petersburg": "saint petersburg", "st. petersburg": "saint petersburg",
              "quebec city": "quebec", "mallorca": "palma", "bali": "denpasar", "flushing meadows": "new york city",
              "new york": "new york city", "cincinnatti": "cincinnati", "cincinatti": "cincinnati",
              "costa do sauipe": "salvador", "los cobos": "cabo san lucas", "los cabos": "cabo san lucas",
              "tenerife": "santa cruz de tenerife", "nuevo vallarta": "puerto vallarta", "hersonissos": "irakleion",
              "chersonissos": "irakleion", "sharm elsheikh": "sharm el sheikh", "maanshan": "ma anshan", "sharm el-sheikh": "sharm el sheikh", "heraklion": "irakleion", "s'hertogenbosch": "s hertogenbosch", "'s-hertogenbosch": "s hertogenbosch"}
US_STATES = {"connecticut": "America/New_York", "north carolina": "America/New_York", "ohio": "America/New_York",
             "new york": "America/New_York", "florida": "America/New_York", "california": "America/Los_Angeles",
             "texas": "America/Chicago", "illinois": "America/Chicago", "massachusetts": "America/New_York",
             "rhode island": "America/New_York", "georgia": "America/New_York", "arizona": "America/Phoenix",
             "washington dc": "America/New_York", "district of columbia": "America/New_York",
             "south carolina": "America/New_York", "colorado": "America/Denver", "nevada": "America/Los_Angeles"}


US_ABBR = {"OH": "America/New_York", "FL": "America/New_York", "GA": "America/New_York", "NC": "America/New_York",
           "SC": "America/New_York", "NY": "America/New_York", "NJ": "America/New_York", "PA": "America/New_York",
           "VA": "America/New_York", "MD": "America/New_York", "MA": "America/New_York", "CT": "America/New_York",
           "MI": "America/Detroit", "KY": "America/New_York", "TN": "America/Chicago", "AL": "America/Chicago",
           "TX": "America/Chicago", "IL": "America/Chicago", "MO": "America/Chicago", "LA": "America/Chicago",
           "OK": "America/Chicago", "MN": "America/Chicago", "WI": "America/Chicago", "KS": "America/Chicago",
           "CO": "America/Denver", "UT": "America/Denver", "NM": "America/Denver", "AZ": "America/Phoenix",
           "CA": "America/Los_Angeles", "NV": "America/Los_Angeles", "OR": "America/Los_Angeles",
           "WA": "America/Los_Angeles", "HI": "Pacific/Honolulu", "IN": "America/Indiana/Indianapolis"}
# countries with more than one clock where tennis is almost always played in one of them
COUNTRY_DEFAULT = {"ES": "Europe/Madrid", "PT": "Europe/Lisbon"}


def _code(country: str) -> str | None:
    c = (country or "").strip()
    return geo.COUNTRY_CODE.get(c) or EXTRA_CODES.get(c)


@lru_cache(maxsize=2000)
def venue_tz(venue: str) -> str | None:
    """IANA timezone of an ESPN venue, or None if it cannot be placed."""
    venue = re.sub(r"\.\s+(?=[^,.]+$)", ", ", venue or "")      # "Basel. Switzerland"
    parts = [p.strip() for p in venue.split(",") if p.strip()]
    if not parts:
        return None
    try:
        c = geo.cities()
    except Exception:  # noqa: BLE001 - cities table not downloaded
        return None
    if len(parts) > 1 and parts[-1].upper() in US_ABBR:          # "Columbus, OH"
        return US_ABBR[parts[-1].upper()]
    code = _code(parts[-1])
    if code is None:                 # no country given ("Kuala Lumpur"): the most populous city of that name anywhere
        k = geo.norm(CITY_ALIAS.get(parts[-1].lower(), parts[-1]))
        hit = c[c.key == k].sort_values("population", ascending=False)
        if not len(hit):           # "Matsuyama" → "Matsuyama-shi"
            hit = c[c.key.str.startswith(k + " ")].sort_values("population", ascending=False)
        return str(hit.iloc[0].timezone) if len(hit) and isinstance(hit.iloc[0].timezone, str) else None
    rows = c[c.country_code == code]
    for name in parts[:-1]:
        low = name.lower().strip()
        if code == "US" and low in US_STATES:
            return US_STATES[low]
        k = geo.norm(CITY_ALIAS.get(low, name))
        hit = rows[rows.key == k]
        if not len(hit):           # "Acapulco" → "Acapulco de Juárez"
            hit = rows[rows.key.str.startswith(k + " ")].sort_values("population", ascending=False)
        if len(hit) and isinstance(hit.iloc[0].timezone, str):
            return str(hit.iloc[0].timezone)
    # only the country (or the city is unknown): its timezone if the whole country keeps one clock
    zones = rows.sort_values("population", ascending=False).timezone.dropna().head(40).unique()
    if len(zones) == 0:
        return None
    clocks = set()
    for z in zones:
        try:
            clocks.add(tuple(datetime(2026, mo, 1, 12, tzinfo=ZoneInfo(z)).utcoffset() for mo in (1, 7)))
        except Exception:  # noqa: BLE001
            continue
    return str(zones[0]) if len(clocks) == 1 else COUNTRY_DEFAULT.get(code)


ESPN_TZ = ZoneInfo("America/New_York")


def _dt(when) -> datetime:
    if isinstance(when, str):
        when = datetime.fromisoformat(when.replace("Z", "+00:00"))
    if hasattr(when, "to_pydatetime"):
        when = when.to_pydatetime()
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def date_only(when) -> bool:
    """ESPN's placeholder for 'time not set yet': midnight US Eastern (05:00 GMT in winter, 04:00 in summer)."""
    et = _dt(when).astimezone(ESPN_TZ)
    return et.hour == 0 and et.minute == 0


def day_start_utc(venue: str, day: str) -> datetime:
    """Midnight at the venue on a day, in UTC (UTC midnight if the venue's timezone is unknown)."""
    tz = venue_tz(venue or "")
    d = datetime.fromisoformat(day[:10])
    return d.replace(tzinfo=ZoneInfo(tz) if tz else timezone.utc).astimezone(timezone.utc)


def local_time(venue: str, when) -> tuple[str | None, str | None]:
    """('HH:MM' at the venue, timezone) for a known start time; (None, tz) for ESPN's date-only placeholder."""
    tz = venue_tz(venue or "")
    w = _dt(when)
    if date_only(w):
        return None, tz
    return (w.astimezone(ZoneInfo(tz)) if tz else w.astimezone(timezone.utc)).strftime("%H:%M"), tz


def local_day(venue: str, when) -> tuple[str, str | None]:
    """(calendar day at the venue 'YYYY-MM-DD', timezone or None). Unknown venues fall back to the UTC day. ESPN's
    date-only placeholder (midnight US Eastern) means "that date, time not set", so it keeps ESPN's date."""
    when = _dt(when)
    tz = venue_tz(venue or "")
    if date_only(when):
        return when.astimezone(ESPN_TZ).strftime("%Y-%m-%d"), tz
    if tz:
        try:
            return when.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d"), tz
        except Exception:  # noqa: BLE001 - unknown zone name
            pass
    return when.astimezone(timezone.utc).strftime("%Y-%m-%d"), None


def noon_utc_hour(day: str, tz: str | None) -> float:
    """Noon at the venue on that day, as an hour of the UTC day (can be negative or above 24)."""
    if not tz:
        return 12.0
    d = datetime.fromisoformat(day[:10]).replace(hour=12, tzinfo=ZoneInfo(tz))
    off = d.utcoffset().total_seconds() / 3600
    return 12.0 - off
