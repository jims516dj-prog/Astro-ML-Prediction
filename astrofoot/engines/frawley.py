"""Engine 3 - John Frawley, *Sports Astrology* (2007), ch. 2 "The Chart for the Event".

Tropical zodiac, Placidus houses, traditional rulers. Favourite = Lords 1 and 10;
underdog = Lords 7 and 4. Spec §7. Every testimony carries a doctrine key so the
Doctrine Tribunal can test it individually.
"""
from __future__ import annotations

from .. import ephem
from ..tables import RULER
from .common import Verdict, View, sep, within_after, within_before

ORB = 3.0
STRENGTH = {"strong": 3.0, "medium": 2.0, "weak": 1.0}
FAV_HOUSES, DOG_HOUSES = (1, 10), (7, 4)
ASPECTS = {0: "conjunction", 60: "sextile", 90: "square", 120: "trine", 180: "opposition"}


def _sig_map(v: View) -> dict[str, str]:
    """planet -> 'fav' | 'dog' for Lords 1/10 vs 7/4 (planets ruling both sides are dropped)."""
    roles: dict[str, set] = {}
    for h, side in ((1, "fav"), (10, "fav"), (7, "dog"), (4, "dog")):
        roles.setdefault(v.lord(h), set()).add(side)
    return {p: next(iter(s)) for p, s in roles.items() if len(s) == 1}


def _lord_label(v: View, p: str) -> str:
    return "/".join(f"L{h}" for h in (1, 10, 7, 4) if v.lord(h) == p)


def _placement_testimonies(vd: Verdict, v: View, sig: dict, use_antiscia: bool):
    for p, side in sig.items():
        other = "dog" if side == "fav" else "fav"
        x = float(ephem.antiscion(v.lon[p])) if use_antiscia else v.lon[p]
        tag = "antiscion of " if use_antiscia else ""
        main = p in (v.lord(1), v.lord(7))
        strength = "strong" if main else "medium"
        for h in (1, 10, 7, 4):
            cusp = v.cusps[h - 1]
            own = h in (FAV_HOUSES if side == "fav" else DOG_HOUSES)
            on, inside = within_before(x, cusp, ORB), within_after(x, cusp, ORB)
            if not (on or inside):
                continue
            lbl = f"{tag}{_lord_label(v, p)} ({p})"
            key_base = f"frawley.{'antiscion' if use_antiscia else 'body'}"
            if own:
                vd.add(f"{lbl} {'on' if on else 'just inside'} own cusp {h}", side,
                       STRENGTH["weak"], f"{key_base}.own_cusp")
            elif on:
                s = "weak" if (v.retro(p) and not use_antiscia) else strength
                vd.add(f"{lbl} on enemy cusp {h}{' (retrograde)' if s == 'weak' else ''} — attacks",
                       side, STRENGTH[s], f"{key_base}.on_enemy_cusp")
            else:
                vd.add(f"{lbl} just inside enemy house {h} — captured", other,
                       STRENGTH[strength], f"{key_base}.inside_enemy_house")


def _moon_events(v: View, sig: dict, travel_limit: float):
    """Moon's applying aspects within `travel_limit` degrees of its own motion, sorted."""
    mo, ms = v.lon["Mo"], v.spd["Mo"]
    events = []
    targets = {p: (v.lon[p], v.spd[p], "body") for p in sig}
    targets.update({f"{p}*": (float(ephem.antiscion(v.lon[p])), -v.spd[p], "antiscion")
                    for p in sig})
    targets["PF"] = (v.pof, 0.0, "fortuna")
    targets["PF*"] = (float(ephem.antiscion(v.pof)), 0.0, "fortuna")
    for name, (x, s, kind) in targets.items():
        rel = ms - s
        if rel <= 0:
            continue
        angles = (0,) if kind == "antiscion" else ASPECTS
        for a in angles:
            for tgt in {(x + a) % 360, (x - a) % 360}:
                gap = (tgt - mo) % 360            # degrees of relative motion to perfection
                moon_travel = gap * ms / rel
                if moon_travel <= travel_limit:
                    events.append((moon_travel, name, a, kind))
    return sorted(events)


def analyse(rc: dict, *, draw_possible: bool = True, extra_time: bool = False,
            equal_odds: bool = False) -> Verdict:
    vd = Verdict("frawley", "fav")
    if equal_odds:
        vd.winner = "disabled"
        vd.caveats.append("Frawley's event-chart method requires a clear favourite; disabled.")
        return vd
    v = View(rc, "tropical", "placidus")
    if rc.get("polar"):
        vd.caveats.append("Venue above the polar circle: Placidus undefined (Porphyry used).")
    sig = _sig_map(v)

    # Step 1-2: house placement of significators, bodily and by antiscion
    _placement_testimonies(vd, v, sig, use_antiscia=False)
    _placement_testimonies(vd, v, sig, use_antiscia=True)

    # Step 3: Moon placement (body and antiscion)
    for x, tag in ((v.lon["Mo"], "Moon"), (float(ephem.antiscion(v.lon["Mo"])), "Moon antiscion")):
        for h in (1, 10, 7, 4):
            c = v.cusps[h - 1]
            if within_before(x, c, ORB) or within_after(x, c, ORB):
                side = "fav" if h in FAV_HOUSES else "dog"
                vd.add(f"{tag} at cusp {h}", side, STRENGTH["medium"], "frawley.moon_on_cusp")

    # Step 4: antiscion of Fortuna near an angle
    pf_a = float(ephem.antiscion(v.pof))
    for h, side in ((1, "fav"), (7, "fav"), (10, "fav"), (4, "dog")):
        if sep(pf_a, v.cusps[h - 1]) <= ORB:
            vd.add(f"Antiscion of Fortuna on cusp {h}", side, STRENGTH["strong"],
                   f"frawley.fortuna_antiscion_cusp{h}")
    if sep(v.pof, v.lon["Su"]) <= 2.0:
        vd.add("Fortuna combust", "dog", STRENGTH["medium"], "frawley.fortuna_combust")

    # Step 5-6: Moon's applying aspects; aspects to Fortuna and bodily conjunctions are final
    limit = 5.0 + (1.0 if extra_time else 0.0)
    limit = min(limit, 30.0 - (v.lon["Mo"] % 30.0))        # never leave the Moon's sign
    last = None
    for travel, name, a, kind in _moon_events(v, sig, limit):
        if kind == "fortuna":
            side = "fav" if a in (0, 60, 120) else "dog"
            vd.add(f"Moon {ASPECTS[a]} {'antiscion of ' if name == 'PF*' else ''}Fortuna (final)",
                   side, STRENGTH["strong"], "frawley.moon_aspect_fortuna")
            last = None
            break
        p = name.rstrip("*")
        last = (travel, p, a, kind)
        if kind == "body" and a == 0:
            break
    if last:
        travel, p, a, kind = last
        side = sig[p]
        vd.add(f"Moon's last aspect: {ASPECTS[a]} {'antiscion of ' if kind == 'antiscion' else ''}"
               f"{_lord_label(v, p)} ({p})", side, STRENGTH["strong"], "frawley.moon_last_aspect")
        vd.features["late_goal"] = travel > 0.7 * limit
    else:
        vd.features["late_goal"] = False

    # Step 6 (lords): L1 / L7 aspects to Fortuna
    for p, role in ((v.lord(1), "L1"), (v.lord(7), "L7")):
        for x, a_tag in ((v.pof, ""), (pf_a, "antiscion of ")):
            if sep(v.lon[p], x) <= ORB:
                side = "fav" if role == "L1" else "dog"
                vd.add(f"{role} conjunct {a_tag}Fortuna", side, STRENGTH["medium"],
                       f"frawley.{role.lower()}_conj_fortuna")
            elif abs(sep(v.lon[p], x) - 180) <= ORB:
                if role == "L1":
                    side = "dog"
                else:   # Frawley's anomaly: L7 bodily opposite Fortuna favours underdog
                    side = "dog" if not a_tag else "fav"
                vd.add(f"{role} opposite {a_tag}Fortuna", side, STRENGTH["medium"],
                       f"frawley.{role.lower()}_opp_fortuna")

    # Step 7: dispositor of Fortuna applying to Fortuna
    disp = RULER[ephem.sign_of(v.pof)]
    if disp not in (v.lord(1), v.lord(7), "Mo"):
        d = float(ephem.angdiff(v.pof, v.lon[disp]))
        applying = v.spd[disp] * d > 0
        if applying and abs(d) <= 5:
            vd.add(f"Dispositor of Fortuna ({disp}) applying to conjunction", "fav",
                   STRENGTH["medium"], "frawley.dispositor_conj_fortuna")
        d_opp = float(ephem.angdiff((v.pof + 180) % 360, v.lon[disp]))
        if v.spd[disp] * d_opp > 0 and abs(d_opp) <= 5:
            vd.add(f"Dispositor of Fortuna ({disp}) applying to opposition", "dog",
                   STRENGTH["medium"], "frawley.dispositor_opp_fortuna")

    # Step 8: miscellaneous
    for p, side in sig.items():
        other = "dog" if side == "fav" else "fav"
        if sep(v.lon["Ra"], v.lon[p]) <= ORB:
            vd.add(f"North Node on {_lord_label(v, p)}", side, STRENGTH["weak"], "frawley.north_node")
        if sep(v.lon["Ke"], v.lon[p]) <= ORB:
            vd.add(f"South Node on {_lord_label(v, p)}", other, STRENGTH["weak"], "frawley.south_node")
        if p != "Su" and 17 / 60 < sep(v.lon["Su"], v.lon[p]) <= 2.0:
            vd.add(f"{_lord_label(v, p)} combust", other, STRENGTH["medium"], "frawley.combust")
        if p != "Sa" and "Sa" not in (v.lord(1), v.lord(7)) and sep(v.lon["Sa"], v.lon[p]) <= ORB:
            vd.add(f"Saturn afflicts {_lord_label(v, p)}", other, STRENGTH["weak"], "frawley.saturn")
    pl = v.lon["Pl"]
    if within_before(pl, v.cusps[0], ORB) or sep(pl, v.cusps[0]) <= 1.0:
        vd.add("Pluto on the 1st cusp", "dog", STRENGTH["medium"], "frawley.pluto_cusp1")
    if within_before(pl, v.cusps[1], ORB):
        vd.add("Pluto on the 2nd cusp", "dog", STRENGTH["weak"], "frawley.pluto_cusp2")
    for x in (v.pof, pf_a):
        if sep(pl, x) <= ORB or abs(sep(pl, x) - 180) <= ORB:
            vd.add("Pluto conjunct/opposite Fortuna", "dog", STRENGTH["medium"], "frawley.pluto_fortuna")
            break
    if within_before(v.lon["Ur"], v.cusps[9], ORB):
        vd.add("Uranus applying to the MC", "fav", STRENGTH["strong"], "frawley.uranus_mc")
    if sep(v.lon["Ur"], v.pof) <= ORB:
        vd.add("Uranus conjunct Fortuna", "fav", STRENGTH["medium"], "frawley.uranus_conj_fortuna")
    if abs(sep(v.lon["Ur"], v.pof) - 180) <= ORB:
        vd.add("Uranus opposite Fortuna", "dog", STRENGTH["medium"], "frawley.uranus_opp_fortuna")

    # Step 9: verdict
    n_fav = sum(1 for t in vd.testimonies if t.side == "fav")
    n_dog = len(vd.testimonies) - n_fav
    if not vd.testimonies:
        vd.winner = "fav"
        vd.caveats.append("No testimony: default rule — the favourite wins.")
    elif vd.net == 0 and draw_possible:
        vd.winner = "draw"
    else:
        vd.winner = "fav" if vd.net >= 0 else "dog"
    if vd.winner == "draw":
        vd.goals_fav = vd.goals_dog = 1
    else:
        n_win, n_lose = (n_fav, n_dog) if vd.winner == "fav" else (n_dog, n_fav)
        w, lo = min(1 + n_win // 2, 4), (1 if n_lose else 0)
        lo = min(lo, w - 1)
        vd.goals_fav, vd.goals_dog = (w, lo) if vd.winner == "fav" else (lo, w)
    strong = sum(1 for t in vd.testimonies if t.points >= 3 and t.side == vd.winner)
    vd.confidence = "high" if strong >= 2 else "medium" if strong == 1 else "low"
    vd.features.update({"testimony_count": len(vd.testimonies), "net": vd.net,
                        "pluto_on_1st": any(t.key == "frawley.pluto_cusp1" for t in vd.testimonies)})
    return vd
