"""Engine 1 - Dr Ravi Rao, *Sports Astrology: The Inclusive Methodology* (2017). Spec §5.

Sidereal Lahiri, Whole Sign houses, favourite = Lagna. Rao's 0-3 point judgement is
interpretive; this module makes it explicit and reproducible:

  planet score: exalted / own sign 3 · friend's sign 2 · neutral 1 · enemy / debilitated 0,
                then +1 per benefic and -1 per malefic conjoining or aspecting it (clipped 0..3)
  house score : no influence 1 · benefic-only 2 · Jupiter/strong benefic occupant 3 ·
                malefic-only 0 · mixed 1

Nations' charts (step 2) run only when founding charts are supplied; Planetary Influence
(step 3) runs only when captain/jersey data is supplied. Skips are reported as caveats.
"""
from __future__ import annotations

from datetime import datetime

from .. import ephem
from ..tables import (BENEFICS, GRAHA_DRISHTI, JERSEY_COLOR_PLANET, MALEFICS, NUMBER_PLANET,
                      RULER, WEEKDAY_LORD, relation)
from .common import Verdict, View

GRAHAS = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
PARAMS = [  # (label, native house(s), rival house(s), doctrine key)
    ("Ascendant", (1,), (7,), "asc"),
    ("Ascendant lord", "L1", "L7", "asc_lord"),
    ("Score", (10,), (4,), "score"),
    ("Game + Coach & Captain", (5, 3), (11, 9), "game_coach"),
    ("Fans & Odds", (2,), (8,), "fans"),
    ("Penalties", (12,), (6,), "penalties"),
]


def _nature(v: View, p: str) -> str:
    if p == "Mo":
        return "benefic" if v.moon_phase() < 180 else "malefic"     # waxing / waning
    return "benefic" if p in BENEFICS else "malefic"


def _aspected_houses(v: View, p: str) -> set[int]:
    h = v.house(p)
    return {(h - 1 + k - 1) % 12 + 1 for k in GRAHA_DRISHTI.get(p, (7,))}


def _influences(v: View, house: int, exclude: str | None = None):
    ben, mal = [], []
    for p in GRAHAS:
        if p == exclude:
            continue
        if v.house(p) == house or house in _aspected_houses(v, p):
            (ben if _nature(v, p) == "benefic" else mal).append(p)
    return ben, mal


def _planet_score(v: View, p: str) -> int:
    if v.exalted(p) or v.own_sign(p):
        s = 3
    elif v.debilitated(p):
        s = 0
    else:
        s = {"friend": 2, "neutral": 1, "enemy": 0}[relation(p, RULER[v.sign(p)])]
    ben, mal = _influences(v, v.house(p), exclude=p)
    return max(0, min(3, s + len(ben) - len(mal)))


def _house_score(v: View, h: int) -> int:
    ben, mal = _influences(v, h)
    occ = [p for p in GRAHAS if v.house(p) == h]
    strong = any(p == "Ju" or (p in ben and (v.exalted(p) or v.own_sign(p))) for p in occ)
    if ben and not mal:
        return 3 if strong else 2
    if mal and not ben:
        return 0
    return 1


def _nation_points(v: View, natal: View) -> tuple[int, int, bool]:
    """Transpose nation Moon and Ascendant onto the match chart. Returns (moon, asc, saturn8)."""
    pts = []
    for x in (natal.lon["Mo"], natal.asc):
        h = ephem.house_of(x, v.cusps)
        ben, mal = _influences(v, h)
        heavy = [p for p in mal if p in ("Sa", "Ma")]
        pts.append(0 if heavy and "Ju" not in ben else 2 if ben and not mal else 1 + ("Ju" in ben))
    # transit Saturn's house in the team chart, and the houses its 3/7/10 drishti reaches
    sat_house = ephem.house_of(v.lon["Sa"], natal.cusps)
    saturn8 = 8 in {(sat_house - 1 + k - 1) % 12 + 1 for k in (3, 7, 10)} or sat_house == 8
    return min(pts[0], 3), min(pts[1], 3), saturn8


def _digit(n: int) -> int:
    while n > 9:
        n = sum(int(c) for c in str(n))
    return n


def _influence_points(jersey: int | None, color: str | None, when: datetime) -> tuple[int, list[str]]:
    notes, pts = [], 0
    day_lord = WEEKDAY_LORD[when.weekday()]
    date_planet = NUMBER_PLANET[_digit(when.day)] if when.day else None
    if jersey:
        jp = NUMBER_PLANET[_digit(jersey)]
        rel_date = relation(jp, date_planet)
        rel_day = relation(jp, day_lord)
        pts += {"friend": 1, "neutral": 0.5, "enemy": 0}[rel_date]
        pts += {"friend": 1, "neutral": 0.5, "enemy": 0}[rel_day]
        if _digit(jersey) in (9, 7):
            pts += 1
        elif _digit(jersey) in (8, 4, 2):
            pts -= 0.5
        notes.append(f"captain #{jersey} → {jp}; date {date_planet} ({rel_date}), day {day_lord} ({rel_day})")
    if color and color.lower() in JERSEY_COLOR_PLANET:
        cp = JERSEY_COLOR_PLANET[color.lower()]
        r = relation(cp, day_lord)
        pts += {"friend": 1, "neutral": 0.5, "enemy": 0}[r]
        notes.append(f"jersey {color} → {cp} vs day lord {day_lord}: {r}")
    return int(round(max(0, min(3, pts)))), notes


def analyse(rc: dict, *, draw_possible: bool = True, when: datetime | None = None,
            natal_fav: dict | None = None, natal_dog: dict | None = None,
            captain: dict | None = None) -> Verdict:
    """`captain` = {"fav_jersey", "dog_jersey", "fav_color", "dog_color"} or None."""
    vd = Verdict("rao", "fav")
    v = View(rc, "lahiri", "whole_sign")
    for label, nat, riv, key in PARAMS:
        if nat == "L1":
            pf, pd = _planet_score(v, v.lord(1)), _planet_score(v, v.lord(7))
        else:
            pf = round(sum(_house_score(v, h) for h in nat) / len(nat))
            pd = round(sum(_house_score(v, h) for h in riv) / len(riv))
        vd.table.append({"parameter": label, "fav": pf, "dog": pd})
        vd.score_fav += pf
        vd.score_dog += pd
        if pf != pd:
            vd.add(f"{label}: {pf} vs {pd}", "fav" if pf > pd else "dog", 0, f"rao.{key}")

    if natal_fav and natal_dog:
        nf, nd = View(natal_fav, "lahiri", "whole_sign"), View(natal_dog, "lahiri", "whole_sign")
        mf, af, s8f = _nation_points(v, nf)
        md, ad, s8d = _nation_points(v, nd)
        for label, pf, pd, key in (("Nation Moon", mf, md, "nation_moon"), ("Nation Ascendant", af, ad, "nation_asc")):
            vd.table.append({"parameter": label, "fav": pf, "dog": pd})
            vd.score_fav += pf
            vd.score_dog += pd
            if pf != pd:
                vd.add(f"{label}: {pf} vs {pd}", "fav" if pf > pd else "dog", 0, f"rao.{key}")
        if s8f or s8d:
            vd.caveats.append("Saturn aspects the 8th house of a team chart: interruption risk. "
                              "If the match is interrupted, Rao's method must be set aside.")
            vd.features["saturn_8th"] = True
    else:
        vd.caveats.append("Nations' Charts phase skipped — founding charts not provided.")

    if captain and when:
        fp, fnotes = _influence_points(captain.get("fav_jersey"), captain.get("fav_color"), when)
        dp, dnotes = _influence_points(captain.get("dog_jersey"), captain.get("dog_color"), when)
        vd.table.append({"parameter": "Planetary influence", "fav": fp, "dog": dp,
                         "notes": "; ".join(fnotes + dnotes)})
        vd.score_fav += fp
        vd.score_dog += dp
        if fp != dp:
            vd.add(f"Planetary influence: {fp} vs {dp}", "fav" if fp > dp else "dog", 0, "rao.influence")
        vd.features["influence_included"] = True
    else:
        vd.table.append({"parameter": "Planetary influence", "fav": None, "dog": None, "notes": "skipped"})
        vd.caveats.append("Planetary influence layer skipped — captain/jersey data not provided.")
        vd.features["influence_included"] = False

    diff = vd.net
    if diff == 0:
        vd.winner = "draw" if draw_possible else "fav"
    else:
        vd.winner = "fav" if diff > 0 else "dog"
    margin = abs(diff)
    if vd.winner == "draw":
        vd.goals_fav = vd.goals_dog = 1
    else:
        w = 1 if margin <= 3 else 2 if margin < 8 else 3
        lo = 1 if margin <= 3 else 0
        vd.goals_fav, vd.goals_dog = (w + lo, lo) if vd.winner == "fav" else (lo, w + lo)
    vd.confidence = "high" if margin >= 8 else "medium" if margin >= 4 else "low"
    vd.features.update({"point_diff": diff, "saturn_8th": vd.features.get("saturn_8th", False)})
    return vd
