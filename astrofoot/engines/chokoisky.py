"""Engine 2 - Simon Chokoisky, *Gambler's Dharma* (2017). Spec §6.

Sidereal Lahiri + Placidus with cuspal degrees; Krishnamurti ayanamsha for sublords only.
Favourite = Lagna, underdog = 7th. Signed multi-tier point total (+ favourite, - underdog).

Not implemented (no reliable inputs): Upaketu/Gulika, Ceres/Chiron, "stolen cusp"
adjustments. They are listed in the verdict caveats so the omission is visible.
"""
from __future__ import annotations

import re

from .. import ephem
from ..tables import (BENEFICS, CHOK_D1, CHOK_D9, DIG_BALA_HOUSE, INVISIBLE, MALEFICS, NAK_LORD,
                      PADA_SYLLABLES, RULER, STARS)
from .common import Verdict, View, sep

FAV_VICTORY = {1, 3, 6, 10, 11}
DOG_VICTORY = {7, 9, 12, 4, 5}
AXIS = {1: 0, 7: 0, 4: 1, 10: 1, 6: 2, 12: 2}
FAV_CUSPS = {1, 10, 6}
# Planets (no outers) used for houses/victory; outers enter only via cuspal strength
CORE = ["Su", "Mo", "Me", "Ve", "Ma", "Ju", "Sa", "Ra", "Ke"]
CUSP_BODIES = CORE + ["Ur", "Ne", "Pl"]


def _exaggerated(v: View, p: str) -> bool:
    full_moon = p == "Mo" and abs(v.moon_phase() - 180) <= 12
    dig = DIG_BALA_HOUSE.get(p) == v.house(p)
    return v.exalted(p) or v.retro(p) or v.own_sign(p) or v.own_nakshatra(p) or dig or full_moon


def _victory_houses(vd: Verdict, v: View):
    for p in CORE:
        h = v.house(p)
        side = "fav" if h in FAV_VICTORY else "dog" if h in DOG_VICTORY else None
        if side is None:
            continue
        if p in MALEFICS:
            strong = v.exalted(p) or v.own_sign(p) or DIG_BALA_HOUSE.get(p) == h
            pts = 2.0 if v.debilitated(p) else 3.0 if strong else 2.5
        elif p in BENEFICS and _exaggerated(v, p):
            pts = 2.0 if v.debilitated(p) else 2.5
        else:
            continue
        vd.add(f"{p} in victory house {h}", side, pts, "chokoisky.victory_house")


def _kartari(vd: Verdict, v: View):
    for axis_house, side, flank in ((1, "fav", (12, 2)), (7, "dog", (6, 8))):
        other = "dog" if side == "fav" else "fav"
        sides = [[p for p in CORE if v.house(p) == h] for h in flank]
        ben = [any(p in BENEFICS for p in s) for s in sides]
        mal = [any(p in MALEFICS for p in s) for s in sides]
        node_only = [bool(s) and all(p in ("Ra", "Ke") for p in s) for s in sides]
        if all(ben) and not any(mal):
            marred = any(p in ("Su", "Ke") for s in sides for p in s)
            vd.add(f"Shubha Kartari Yoga around cusp {axis_house}{' (marred)' if marred else ''}",
                   side, 3.5 if marred else 8.0, "chokoisky.sky")
        elif all(mal) and not any(ben):
            pts = 3.0 if any(node_only) else 6.0
            vd.add(f"Papa Kartari Yoga around cusp {axis_house}", other, pts, "chokoisky.pky")


def _mercury_sign(v: View) -> str:
    ruled = [h for h in range(1, 13) if v.lord(h) == "Me"]
    fav = sum(h in FAV_VICTORY for h in ruled)
    dog = sum(h in DOG_VICTORY for h in ruled)
    return "+" if fav >= dog else "-"


def _effect(code: str, v: View, p: str) -> str:
    if code == "U":
        return "-" if v.retro(p) else "+"
    if code == "N":
        return "+" if v.retro(p) else "-"
    if code == "M":
        return _mercury_sign(v)
    return code


def _cuspal_d1(vd: Verdict, v: View):
    for p in CUSP_BODIES:
        orb = 2.0 if p in INVISIBLE else 2.5
        if v.exalted(p) or v.retro(p):
            orb += 0.5
        for h, ax in AXIS.items():
            if sep(v.lon[p], v.cusps[h - 1]) > orb:
                continue
            eff = _effect(CHOK_D1[p][ax], v, p)
            owner = "fav" if h in FAV_CUSPS else "dog"
            side = owner if eff == "+" else ("dog" if owner == "fav" else "fav")
            vd.add(f"{p} on D1 cusp {h} ({eff})", side, 7.0 if p in INVISIBLE else 8.0,
                   f"chokoisky.d1_cusp.{p}")


def _cuspal_d9(vd: Verdict, v: View):
    asc9 = float(ephem.d9(v.asc))
    for p in CUSP_BODIES:
        x9 = float(ephem.d9(v.lon[p]))
        orb = 2.0 if p in INVISIBLE else 2.5
        for cusp, owner in ((asc9, "fav"), ((asc9 + 180) % 360, "dog")):
            d = sep(x9, cusp)
            if d > orb:
                continue
            eff = _effect(CHOK_D9[p], v, p)
            side = owner if eff == "+" else ("dog" if owner == "fav" else "fav")
            pts = (13.0 if p in INVISIBLE else 16.0) * (1.25 if d < 1.0 else 1.0)
            vd.add(f"{p} on D9 {'1st' if owner == 'fav' else '7th'} cusp ({eff})", side, pts,
                   f"chokoisky.d9_cusp.{p}")
            vd.features["d9_cusp_planet"] = True


def _first_syllable(name: str) -> str:
    s = name.lower()
    s = s.replace("w", "v").replace("f", "p").replace("z", "j").replace("ph", "p")
    return re.sub(r"[^a-z]", "", s)


def _syllable_match(syl: str, name: str) -> bool:
    n = _first_syllable(name)
    if not n:
        return False
    variants = {syl}
    if syl.endswith("e"):
        variants.add(syl[:-1] + "ai")
    if syl.endswith("o"):
        variants.add(syl[:-1] + "au")
    if syl == "a":     # pure vowels match only a leading vowel
        return n[0] == "a"
    return any(n.startswith(x) for x in variants)


def _nama_pada(vd: Verdict, v: View, fav_name: str, dog_name: str):
    _, pada = ephem.nakshatra(v.mc)
    syl = PADA_SYLLABLES[pada]
    vd.features["mc_syllable"] = syl
    for name, side in ((fav_name, "fav"), (dog_name, "dog")):
        if name and _syllable_match(syl, name):
            vd.add(f"Nama pada: MC syllable '{syl}' matches {name}", side, 16.0, "chokoisky.nama_pada")


def _kp_context(kp: View):
    occupants = {h: [] for h in range(1, 13)}
    for p in CORE:
        occupants[kp.house(p)].append(p)
    star = {p: NAK_LORD[ephem.nakshatra(kp.lon[p])[0]] for p in CORE}
    lords = {h: kp.lord(h) for h in range(1, 13)}
    return occupants, star, lords


def _sublord_score(ctx, sub: str, rotate: int) -> float:
    """Signed KP significator score of `sub` from the point of view of house 1+rotate."""
    occupants, star, lords = ctx
    score = 0.0
    for h in range(1, 13):
        rel = (h - 1 - rotate) % 12 + 1          # house counted from the team's own cusp
        weight = 1.0 if rel in FAV_VICTORY else 0.5 if rel == 2 else -1.0
        lord = lords[h]
        pts = 1.0 * (sub == lord) + 2.0 * (star.get(sub) == lord)
        pts += 3.0 * (sub in occupants[h]) + 4.0 * (star.get(sub) in occupants[h])
        score += weight * pts
    return score


def _sublords(vd: Verdict, rc: dict):
    kp = View(rc, "kp", "placidus")
    sub1 = ephem.kp_sublord(kp.cusps[0])[1]
    sub7 = ephem.kp_sublord(kp.cusps[6])[1]
    ctx = _kp_context(kp)
    s1, s7 = _sublord_score(ctx, sub1, 0), _sublord_score(ctx, sub7, 6)
    diff = s1 - s7
    vd.features["sublord_diff"] = diff
    if abs(diff) > 3:
        side = "fav" if diff > 0 else "dog"
        vd.add(f"Sublords: cusp 1 {sub1} ({s1:+.1f}) vs cusp 7 {sub7} ({s7:+.1f})", side,
               min(abs(diff) / 2, 9.0), "chokoisky.sublord")
    subs = [ephem.kp_sublord(c)[1] for c in kp.cusps]
    signs = {1 if _sublord_score(ctx, s, 0) > 0 else -1 for s in subs}
    if len(signs) == 1:
        vd.add("Sublord array: all 12 cusp sublords favour one side",
               "fav" if signs == {1} else "dog", 8.0, "chokoisky.sublord_array")


def _taras(vd: Verdict, v: View):
    hits = {}
    for h in (1, 10, 7, 4):
        side = "fav" if h in (1, 10) else "dog"
        for label, x in ((f"cusp {h}", v.cusps[h - 1]), (f"lord of {h} ({v.lord(h)})", v.lon[v.lord(h)])):
            for star, (pos, pts) in STARS.items():
                d = sep(x, pos)
                if d <= 1.0 and pts != 0:
                    hits.setdefault(star, []).append((d, side, label, pts))
    for star, hs in hits.items():
        d, side, label, pts = min(hs)          # both teams on the same star: closer one counts
        if pts > 0:
            vd.add(f"{label} on {star}", side, pts, f"chokoisky.tara.{star}")
        else:
            vd.add(f"{label} on {star}", "dog" if side == "fav" else "fav", -pts, f"chokoisky.tara.{star}")


_BRIGHTNESS = ["Ve", "Ju", "Ma", "Me", "Sa"]


def _war(vd: Verdict, v: View):
    fav_l = {v.lord(1), v.lord(10)}
    dog_l = {v.lord(7), v.lord(4)}
    for i, a in enumerate(_BRIGHTNESS):
        for b in _BRIGHTNESS[i + 1:]:
            if sep(v.lon[a], v.lon[b]) > 1.0:
                continue
            loser = b                        # list is ordered brightest first
            if loser in fav_l and loser not in dog_l:
                vd.add(f"Planetary war: {a} defeats favourite's lord {loser}", "dog", 5.0, "chokoisky.war")
            elif loser in dog_l and loser not in fav_l:
                vd.add(f"Planetary war: {a} defeats underdog's lord {loser}", "fav", 5.0, "chokoisky.war")


def analyse(rc: dict, fav_name: str = "", dog_name: str = "", *, draw_possible: bool = True) -> Verdict:
    vd = Verdict("chokoisky", "fav")
    vd.features["d9_cusp_planet"] = False
    v = View(rc, "lahiri", "placidus")
    if rc.get("polar"):
        vd.caveats.append("Venue above the polar circle: Placidus undefined (Porphyry used).")
    vd.caveats.append("Not modelled: Upaketu, Gulika, Ceres, Chiron, stolen-cusp adjustments.")
    _victory_houses(vd, v)
    _kartari(vd, v)
    _cuspal_d1(vd, v)
    _cuspal_d9(vd, v)
    _nama_pada(vd, v, fav_name, dog_name)
    _sublords(vd, rc)
    _taras(vd, v)
    _war(vd, v)
    total = vd.net
    if abs(total) <= 3 and draw_possible:
        vd.winner = "draw"
    else:
        vd.winner = "fav" if total > 0 else "dog"
    gd = min(round(abs(total) / 3), 5)
    if vd.winner == "draw":
        vd.goals_fav = vd.goals_dog = 1
    else:
        w = max(gd, 1)
        vd.goals_fav, vd.goals_dog = (w, 0) if vd.winner == "fav" else (0, w)
    vd.confidence = "high" if abs(total) > 9 else "medium" if abs(total) >= 5 else "low"
    vd.table = [{"technique": t.key.split(".")[1], "text": t.text,
                 "points": t.points if t.side == "fav" else -t.points} for t in vd.testimonies]
    vd.features.update({"total": total, "sky": any(t.key == "chokoisky.sky" for t in vd.testimonies),
                        "nama_pada": any(t.key == "chokoisky.nama_pada" for t in vd.testimonies)})
    return vd
