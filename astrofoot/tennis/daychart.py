"""Who is favoured for the day: date-only astrology and numerology.

Birth times are rarely published and match start times move by minutes to hours, so everything here uses
dates only: each player's natal chart for the date of birth (planets at 12:00 UTC) against the sky on the
match day (12:00 UTC). The Moon moves ~13° a day, so it is left out on both sides; the other planets move at
most ~1.5° a day, inside the 3° orb used.

Two readings of each:
- a traditional rule score per player (benefic contacts add, malefic contacts subtract), compared between the
  two players: the higher score is "favoured for the day";
- the raw contacts and numbers as features, so machine learning can learn its own weights (model.py)."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import numpy as np
import swisseph as swe

from . import astro_num as an

PLANETS = ["Su", "Me", "Ve", "Ma", "Ju", "Sa"]
NAMES = {"Su": "Sun", "Me": "Mercury", "Ve": "Venus", "Ma": "Mars", "Ju": "Jupiter", "Sa": "Saturn"}
_IDS = [swe.SUN, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN]
ORB = 3.0
FAMILIES = {"conj": (0,), "harm": (60, 120), "hard": (90, 180)}
ASPECT_NAME = {0: "conjunct", 60: "sextile", 120: "trine", 90: "square", 180: "opposite"}


@lru_cache(maxsize=60000)
def positions(day: str, hour_utc: float = 12.0) -> np.ndarray:
    """Planets on a date at an hour of the UTC day (12.0 = noon UTC; noon at a venue is venue.noon_utc_hour)."""
    d = date.fromisoformat(day[:10])
    jd = swe.julday(d.year, d.month, d.day, hour_utc)
    return np.array([swe.calc_ut(jd, i, swe.FLG_MOSEPH)[0][0] for i in _IDS])


def _sep(t: np.ndarray, n: np.ndarray) -> np.ndarray:
    d = np.abs((t[:, None] - n[None, :]) % 360.0)
    return np.where(d > 180, 360 - d, d)                    # transit × natal separations, 6 × 6


def sky(day: str, tz: str | None = None) -> np.ndarray:
    """The match day's planets at noon at the venue (noon UTC if the venue's timezone is unknown)."""
    from .venue import noon_utc_hour
    return positions(day, noon_utc_hour(day, tz))


def contacts(dob: str, day: str, tz: str | None = None) -> dict[str, np.ndarray]:
    """Strength (1 = exact, 0 = outside the 3° orb) of each transit-to-natal contact, by family."""
    sep = _sep(sky(day, tz), positions(dob))
    return {f: np.max([np.clip(1 - np.abs(sep - a) / ORB, 0, None) for a in angs], axis=0) for f, angs in FAMILIES.items()}


FEATURES = [f"{f}_{t}_{n}" for f in FAMILIES for t in PLANETS for n in PLANETS]


def contact_vector(dob: str | None, day: str, tz: str | None = None) -> np.ndarray:
    dob = an.clean_dob(dob)
    if not dob:
        return np.full(len(FEATURES), np.nan)
    c = contacts(dob, day, tz)
    return np.concatenate([c[f].ravel() for f in FAMILIES])


# traditional weights: (transit, natal) → (conjunction, harmonious, hard)
RULES = {
    ("Ju", "Su"): (1.5, 1.5, -0.5), ("Ju", "Ma"): (1.0, 1.0, -0.3), ("Ju", "Ju"): (1.0, 0.8, -0.3),
    ("Ve", "Su"): (0.8, 0.8, -0.2), ("Ve", "Ve"): (0.5, 0.5, -0.2), ("Ve", "Ma"): (0.5, 0.5, -0.2),
    ("Su", "Su"): (1.0, 0.6, -0.5), ("Su", "Ma"): (0.5, 0.5, -0.3), ("Su", "Ju"): (0.6, 0.5, -0.2),
    ("Ma", "Su"): (0.3, 0.8, -0.8), ("Ma", "Ma"): (0.3, 0.6, -0.6), ("Me", "Ma"): (0.2, 0.3, -0.2),
    ("Sa", "Su"): (-1.5, 0.3, -1.5), ("Sa", "Ma"): (-1.0, 0.2, -1.0), ("Sa", "Ju"): (-0.5, 0.2, -0.5),
}


def astro_day(dob: str | None, day: str, tz: str | None = None) -> dict:
    """Rule score for one player on one day (the calendar day at the venue), with the contacts that made it."""
    dob = an.clean_dob(dob)
    if not dob:
        return {"score": None, "contacts": []}
    t, n = sky(day, tz), positions(dob)
    sep = _sep(t, n)
    score, why = 0.0, []
    for (tp, np_), w in RULES.items():
        i, j = PLANETS.index(tp), PLANETS.index(np_)
        for asp, fam in ((0, 0), (60, 1), (120, 1), (90, 2), (180, 2)):
            s = max(0.0, 1 - abs(sep[i, j] - asp) / ORB)
            if s > 0 and w[fam]:
                score += w[fam] * s
                why.append({"text": f"{NAMES[tp]} {ASPECT_NAME[asp]} natal {NAMES[np_]}",
                            "points": round(float(w[fam] * s), 2), "orb": round(float(abs(sep[i, j] - asp)), 1)})
    # the day's Sun in the same element as the natal Sun
    if an.element(t[0]) == an.element(n[0]):
        score += 0.3
        why.append({"text": f"Sun in a {an.ELEMENT[an.element(t[0])]} sign, like the natal Sun", "points": 0.3, "orb": None})
    why.sort(key=lambda x: -abs(x["points"]))
    return {"score": round(float(score), 3), "contacts": why}


# ----------------------------------------------------------------------------- numerology for the day
GROUPS = ({1, 5, 7}, {2, 4, 8}, {3, 6, 9})     # traditional compatible families


def _compatible(a: int, b: int) -> bool:
    a, b = an.reduce(a), an.reduce(b)
    return any(a in g and b in g for g in GROUPS)


def num_day(dob: str | None, name: str, day: str) -> dict:
    dob = an.clean_dob(dob)
    if not dob:
        return {"score": None, "parts": [], "numbers": {}}
    d = date.fromisoformat(day[:10])
    lp, py, pd_, ud = an.life_path(dob), an.personal_year(dob, d), an.personal_day(dob, d), an.universal_day(d)
    ex = an.expression(name) if isinstance(name, str) and name else None
    parts = []
    if _compatible(pd_, lp):
        parts.append(("Personal day in harmony with the life path", 1.0))
    if pd_ == an.reduce(lp):
        parts.append(("Personal day equals the life path", 1.0))
    if pd_ in (1, 8):
        parts.append((f"Personal day {pd_}: a traditional day of winning and power", 1.0))
    if pd_ in (4, 7):
        parts.append((f"Personal day {pd_}: a traditional day of effort or withdrawal", -0.5))
    if _compatible(ud, lp):
        parts.append(("Universal day in harmony with the life path", 0.5))
    if ex and _compatible(ud, ex):
        parts.append(("Universal day in harmony with the name number", 0.5))
    if py in (1, 8):
        parts.append((f"Personal year {py}: a year of new starts or achievement", 0.5))
    return {"score": round(sum(p for _, p in parts), 2), "parts": [{"text": t, "points": p} for t, p in parts],
            "numbers": {"life_path": lp, "personal_year": py, "personal_day": pd_, "universal_day": ud, "expression": ex}}


NUM_FEATURES = ([f"pd_{k}" for k in range(1, 10)] + [f"lp_{k}" for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33)]
                + [f"py_{k}" for k in range(1, 10)] + [f"ex_{k}" for k in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33)]
                + ["pd_lp_compat", "pd_is_lp", "ud_lp_compat", "ud_ex_compat"])


def num_vector(dob: str | None, name: str, day: str) -> np.ndarray:
    dob = an.clean_dob(dob)
    if not dob:
        return np.full(len(NUM_FEATURES), np.nan)
    d = date.fromisoformat(day[:10])
    lp, py, pd_, ud = an.life_path(dob), an.personal_year(dob, d), an.personal_day(dob, d), an.universal_day(d)
    ex = an.expression(name) if isinstance(name, str) and name else 0
    v = dict.fromkeys(NUM_FEATURES, 0.0)
    v[f"pd_{pd_}"] = v[f"lp_{lp}"] = v[f"py_{py}"] = 1.0
    if ex:
        v[f"ex_{ex}"] = 1.0
    v.update(pd_lp_compat=float(_compatible(pd_, lp)), pd_is_lp=float(pd_ == an.reduce(lp)),
             ud_lp_compat=float(_compatible(ud, lp)), ud_ex_compat=float(bool(ex) and _compatible(ud, ex)))
    return np.array([v[k] for k in NUM_FEATURES])


def verdict(a, b, margin: float = 0.25) -> int:
    """1 if player A is favoured, 2 if B, 0 if level or unknown."""
    if a is None or b is None:
        return 0
    return 1 if a - b > margin else 2 if b - a > margin else 0
