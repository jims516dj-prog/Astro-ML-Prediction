"""Astrological and numerological features of a player on a match day.

Natal charts use the date of birth at 12:00 UTC (birth times are not published), so the Moon can be up
to ~7° off and houses/ascendant are not used. Transits are taken at the match's start time. Every
feature is a plain number per player, so the model can weigh it, or learn it is noise."""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache

import numpy as np
import swisseph as swe

FLAGS = swe.FLG_MOSEPH
BODIES = {"Su": swe.SUN, "Mo": swe.MOON, "Me": swe.MERCURY, "Ve": swe.VENUS, "Ma": swe.MARS, "Ju": swe.JUPITER,
          "Sa": swe.SATURN}
HARMONY = {0: 1.0, 60: 0.5, 120: 1.0, 90: -1.0, 180: -1.0}   # trine/sextile/conjunction vs square/opposition
HARD = (0, 90, 180)
ORB = 6.0
ELEMENT = ["fire", "earth", "air", "water"]


def clean_dob(dob) -> str | None:
    """A usable 'YYYY-MM-DD' or None (missing values arrive as None, NaN or empty strings)."""
    if not isinstance(dob, str) or len(dob) < 10:
        return None
    try:
        date.fromisoformat(dob[:10])
    except ValueError:
        return None
    return dob[:10]


def _jd(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + dt.second / 3600)


@lru_cache(maxsize=50000)
def natal(dob: str) -> tuple:
    d = date.fromisoformat(dob[:10])
    jd = swe.julday(d.year, d.month, d.day, 12.0)
    return tuple(swe.calc_ut(jd, b, FLAGS)[0][0] for b in BODIES.values())


@lru_cache(maxsize=20000)
def transit(hour_key: str) -> tuple:
    """Positions at the match's start, rounded to the hour (cache key 'YYYY-MM-DDTHH')."""
    dt = datetime.fromisoformat(hour_key + ":00:00+00:00")
    jd = _jd(dt)
    return tuple(swe.calc_ut(jd, b, FLAGS)[0][0] for b in BODIES.values())


def _sep(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180 else d


def harmony(a: float, b: float) -> float:
    """+1 for an exact trine/conjunction, -1 for an exact square/opposition, fading to 0 at the orb."""
    d = _sep(a, b)
    return sum(w * max(0.0, 1 - abs(d - asp) / ORB) for asp, w in HARMONY.items())


def hard_hit(a: float, b: float) -> float:
    d = _sep(a, b)
    return max(max(0.0, 1 - abs(d - asp) / ORB) for asp in HARD)


def sign(x: float) -> int:
    return int(x // 30) % 12


def element(x: float) -> int:
    return sign(x) % 4


I = {k: i for i, k in enumerate(BODIES)}
ASTRO_FEATURES = ["solar_return", "birthday_window", "ju_sun", "sa_sun", "ma_sun", "ma_ma", "mo_sun", "ve_ve",
                  "ju_mo", "moon_elem_match", "sun_elem"]


def astro(dob: str | None, when: datetime) -> dict:
    dob = clean_dob(dob)
    if not dob:
        return {k: np.nan for k in ASTRO_FEATURES}
    n, t = natal(dob), transit(when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H"))
    d_sun = _sep(t[I["Su"]], n[I["Su"]])
    return {
        "solar_return": float(np.cos(np.radians(d_sun))),            # 1 on the birthday, -1 six months away
        "birthday_window": float(d_sun <= 10.0),                     # within ~10 days of the birthday
        "ju_sun": harmony(t[I["Ju"]], n[I["Su"]]), "sa_sun": harmony(t[I["Sa"]], n[I["Su"]]),
        "ma_sun": harmony(t[I["Ma"]], n[I["Su"]]), "ma_ma": harmony(t[I["Ma"]], n[I["Ma"]]),
        "mo_sun": harmony(t[I["Mo"]], n[I["Su"]]), "ve_ve": harmony(t[I["Ve"]], n[I["Ve"]]),
        "ju_mo": harmony(t[I["Ju"]], n[I["Mo"]]),
        "moon_elem_match": float(element(t[I["Mo"]]) == element(n[I["Su"]])),
        "sun_elem": float(element(n[I["Su"]])),
    }


def synastry(dob_a: str | None, dob_b: str | None) -> dict:
    """Directional contacts between the two players' charts: A's Mars on B's Sun (pressure on B) and back,
    and whether their Sun elements are compatible (same, or fire-air / earth-water)."""
    dob_a, dob_b = clean_dob(dob_a), clean_dob(dob_b)
    if not dob_a or not dob_b:
        return {"mars_on_opp_sun_a": np.nan, "mars_on_opp_sun_b": np.nan, "sun_compatible": np.nan}
    a, b = natal(dob_a), natal(dob_b)
    ea, eb = element(a[I["Su"]]), element(b[I["Su"]])
    return {"mars_on_opp_sun_a": hard_hit(a[I["Ma"]], b[I["Su"]]), "mars_on_opp_sun_b": hard_hit(b[I["Ma"]], a[I["Su"]]),
            "sun_compatible": float(ea == eb or {ea, eb} in ({0, 2}, {1, 3}))}


# ----------------------------------------------------------------------------- numerology (Pythagorean)
LETTER = {c: (i % 9) + 1 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
NUM_FEATURES = ["life_path", "personal_year", "personal_day", "expression", "pd_is_lp", "pd_power", "ud_is_lp"]


def reduce(n: int, masters: bool = False) -> int:
    while n > 9 and not (masters and n in (11, 22, 33)):
        n = sum(int(c) for c in str(n))
    return n


def _digits(*parts) -> int:
    return sum(int(c) for p in parts for c in str(p) if c.isdigit())


def life_path(dob: str) -> int:
    y, m, d = dob[:10].split("-")
    return reduce(reduce(_digits(y), True) + reduce(_digits(m), True) + reduce(_digits(d), True), True)


def universal_day(day: date) -> int:
    return reduce(_digits(day.year, day.month, day.day))


def personal_year(dob: str, day: date) -> int:
    _, m, d = dob[:10].split("-")
    return reduce(_digits(m, d, day.year))


def personal_day(dob: str, day: date) -> int:
    return reduce(personal_year(dob, day) + reduce(_digits(day.month)) + reduce(_digits(day.day)))


def expression(name: str) -> int:
    return reduce(sum(LETTER.get(c, 0) for c in (name or "").lower()), True)


def numerology(dob: str | None, name: str, day: date) -> dict:
    dob = clean_dob(dob)
    name = name if isinstance(name, str) else ""
    if not dob:
        return {k: np.nan for k in NUM_FEATURES} | {"expression": float(expression(name)) if name else np.nan}
    lp, pdn = life_path(dob), personal_day(dob, day)
    return {"life_path": float(lp), "personal_year": float(personal_year(dob, day)), "personal_day": float(pdn),
            "expression": float(expression(name)) if name else np.nan, "pd_is_lp": float(pdn == reduce(lp)),
            "pd_power": float(pdn in (1, 8)), "ud_is_lp": float(universal_day(day) == reduce(lp))}
