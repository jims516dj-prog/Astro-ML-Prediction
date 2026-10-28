"""The Primitive Lattice (spec §12.4): a tradition-neutral astrological feature matrix.

Built vectorised from a sky (see sky.py). The 1st house always belongs to `team1` of the
active frame, so the same matrix serves the FAV, HOME and COIN frames; only the label and
the market offset are re-oriented.

Blocks (and why they are separated):
  S   zodiac- and house-free sky state: harmonics, speeds, stations, aspects, Moon, hours
  Z   discrete zodiac placements, per zodiac (tropical / Lahiri) - lets the data adjudicate
  A   bodies and their antiscia relative to the four angles (zodiac-free)
  H   house occupancy and team lordship, per house system (x zodiac where it matters)
Every column carries metadata used by the Codex to state a rule in astrological language.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import ephem
from .config import LATTICE_VERSION, REF
from .tables import (BODIES, BODY_NAMES, CHALDEAN, DEBIL, DETRIMENT, EXALT, MEAN_SPEED,
                     NAKSHATRAS, OWN_SIGNS, PTOLEMAIC, RULER, SIGN_NAMES)

B = {b: i for i, b in enumerate(BODIES)}
PLANETS10 = ["Su", "Mo", "Me", "Ve", "Ma", "Ju", "Sa", "Ur", "Ne", "Pl"]
CLASSICAL = ["Su", "Mo", "Me", "Ve", "Ma", "Ju", "Sa"]
ANGLES = {"Asc": 0, "MC": 9, "Dsc": 6, "IC": 3}            # cusp index
ANGLE_TEAM = {"Asc": "team1's Ascendant", "MC": "team1's MC (10th)",
              "Dsc": "team2's Descendant (7th)", "IC": "team2's IC (4th)"}
ZODIACS = ["tropical", "lahiri"]
HOUSES = ["placidus", "equal", "regiomontanus", "campanus", "whole_sign"]
ASPECT_SIGMA = 2.5
ANGLE_DECAY = 2.0

META: dict[str, dict] = {}


def _m(name, desc, family, block, structure=None, kind="kernel"):
    META[name] = {"desc": desc, "family": family, "block": block, "structure": structure, "kind": kind}
    return name


def _sep(a, b):
    return np.abs(ephem.angdiff(a, b))


@lru_cache(maxsize=1)
def eclipse_table() -> np.ndarray:
    p = REF / "eclipses.npy"
    if p.exists():
        return np.load(p)
    ev = ephem.eclipses(2454000.0, 2463000.0)      # 2006 .. 2031
    arr = np.array([(jd, 0 if k == "solar" else 1, lon) for jd, k, lon in ev])
    np.save(p, arr)
    return arr


def _lon(sky, z):
    ay = 0.0 if z == "tropical" else sky["ayan_lahiri"][:, None]
    lon = ephem.norm360(sky["blon"] - ay)
    return lon


def _pof(sky):
    """Part of Fortune, tropical (Asc + Moon - Sun); shifting zodiac shifts it like any body."""
    return ephem.norm360(sky["asc"] + sky["blon"][:, B["Mo"]] - sky["blon"][:, B["Su"]])


def _points(sky):
    """Tropical longitudes of bodies + Part of Fortune, shape (n, 12)."""
    return np.column_stack([sky["blon"], _pof(sky)])


POINTS = BODIES + ["PF"]


def block_S(sky) -> dict[str, np.ndarray]:
    f = {}
    lon = sky["blon"]
    spd = sky["bspd"]
    for b in BODIES:
        th = np.radians(lon[:, B[b]])
        for k in (1, 2, 3, 4, 12):
            f[_m(f"S.{b}.h{k}.sin", f"{BODY_NAMES[b]} zodiacal harmonic {k} (sine)", "F1 celestial state",
                 "S", kind="harmonic")] = np.sin(k * th)
            f[_m(f"S.{b}.h{k}.cos", f"{BODY_NAMES[b]} zodiacal harmonic {k} (cosine)", "F1 celestial state",
                 "S", kind="harmonic")] = np.cos(k * th)
    for b in ["Me", "Ve", "Ma", "Ju", "Sa", "Ur", "Ne", "Pl"]:
        r = spd[:, B[b]] / MEAN_SPEED[b]
        f[_m(f"S.{b}.retro", f"{BODY_NAMES[b]} retrograde", "F1 celestial state", "S", kind="flag")] = (r < 0).astype(float)
        f[_m(f"S.{b}.station", f"{BODY_NAMES[b]} near its station", "F1 celestial state", "S")] = np.exp(-np.abs(r) / 0.1)
    for b in ["Mo", "Me", "Ve", "Ma"]:
        f[_m(f"S.{b}.oob", f"{BODY_NAMES[b]} out of bounds (declination beyond 23°27′)", "F1 celestial state",
             "S", kind="flag")] = (np.abs(sky["bdec"][:, B[b]]) > 23.44).astype(float)
    for b in ["Me", "Ve", "Ma", "Ju", "Sa"]:
        d = _sep(lon[:, B[b]], lon[:, B["Su"]])
        f[_m(f"S.{b}.combust", f"{BODY_NAMES[b]} combust (close to the Sun)", "F2 dignity & condition", "S")] = \
            np.exp(-0.5 * (d / 4.0) ** 2)
    for i, a in enumerate(PLANETS10):
        for b2 in PLANETS10[i + 1:]:
            d = _sep(lon[:, B[a]], lon[:, B[b2]])
            for ang, nm in PTOLEMAIC.items():
                f[_m(f"S.asp.{a}-{b2}.{ang}", f"{BODY_NAMES[a]} {nm} {BODY_NAMES[b2]}", "F3 inter-planetary", "S")] = \
                    np.exp(-0.5 * ((d - ang) / ASPECT_SIGMA) ** 2)
    for b2 in PLANETS10:
        d = _sep(lon[:, B["Ra"]], lon[:, B[b2]])
        f[_m(f"S.asp.Ra-{b2}.0", f"North Node conjunct {BODY_NAMES[b2]}", "F3 inter-planetary", "S")] = \
            np.exp(-0.5 * (d / ASPECT_SIGMA) ** 2)
        f[_m(f"S.asp.Ke-{b2}.0", f"South Node conjunct {BODY_NAMES[b2]}", "F3 inter-planetary", "S")] = \
            np.exp(-0.5 * ((180 - d) / ASPECT_SIGMA) ** 2)
    # Moon
    phase = np.radians(ephem.norm360(lon[:, B["Mo"]] - lon[:, B["Su"]]))
    for k in (1, 2):
        f[_m(f"S.moon.phase.h{k}.sin", f"Moon phase harmonic {k} (sine: waxing vs waning)", "F6 Moon process",
             "S", kind="harmonic")] = np.sin(k * phase)
        f[_m(f"S.moon.phase.h{k}.cos", f"Moon phase harmonic {k} (cosine: full vs new)", "F6 Moon process",
             "S", kind="harmonic")] = np.cos(k * phase)
    f[_m("S.moon.speed", "Moon fast in motion", "F6 Moon process", "S", kind="continuous")] = \
        spd[:, B["Mo"]] / MEAN_SPEED["Mo"] - 1
    f[_m("S.moon.voc", "Moon void of course (no further Ptolemaic aspect before leaving its sign)",
         "F6 Moon process", "S", kind="flag")] = _moon_voc(lon, spd).astype(float)
    # Time lords and sky events
    hl = sky["hour_lord"]
    for i, p in enumerate(CHALDEAN):
        f[_m(f"S.hour.{p}", f"planetary hour of {BODY_NAMES[p]}", "F7 time lords", "S", kind="flag")] = (hl == i).astype(float)
    f[_m("S.sun_horizon", "kickoff within ~30 min of sunrise/sunset (sandhi)", "F10 sky events", "S")] = \
        np.exp(-np.nan_to_num(sky["sun_edge_min"], nan=1e4) / 30.0)
    ecl = eclipse_table()
    for code, nm in ((0, "solar"), (1, "lunar")):
        e = ecl[ecl[:, 1] == code, 0]
        idx = np.clip(np.searchsorted(e, sky["jd"]), 1, len(e) - 1)
        days = np.minimum(np.abs(sky["jd"] - e[idx - 1]), np.abs(e[idx] - sky["jd"]))
        f[_m(f"S.eclipse.{nm}", f"within days of a {nm} eclipse", "F10 sky events", "S")] = np.exp(-days / 3.0)
    return f


def _moon_voc(lon, spd):
    mo, ms = lon[:, B["Mo"]], spd[:, B["Mo"]]
    to_end = 30 - mo % 30
    soonest = np.full(len(mo), np.inf)
    for p in ["Su", "Me", "Ve", "Ma", "Ju", "Sa"]:
        rel = ms - spd[:, B[p]]
        for ang in PTOLEMAIC:
            for s in (1, -1):
                gap = (lon[:, B[p]] + s * ang - mo) % 360
                soonest = np.minimum(soonest, gap * ms / rel)
    return soonest > to_end


def block_Z(sky, z: str) -> dict[str, np.ndarray]:
    f = {}
    lon = _lon(sky, z)
    zname = "tropical" if z == "tropical" else "sidereal (Lahiri)"
    sign = (lon // 30).astype(int) % 12
    for b in CLASSICAL + ["Ra"]:
        for s in range(12):
            f[_m(f"Z.{z}.{b}.sign.{s}", f"{BODY_NAMES[b]} in {SIGN_NAMES[s]}", "F2 dignity & condition", "Z", z,
                 kind="flag")] = (sign[:, B[b]] == s).astype(float)
    for b in CLASSICAL:
        sb = sign[:, B[b]]
        for nm, signs in (("domicile", OWN_SIGNS[b]), ("exaltation", [EXALT[b]]),
                          ("detriment", DETRIMENT[b]), ("fall", [DEBIL[b]])):
            f[_m(f"Z.{z}.{b}.{nm}", f"{BODY_NAMES[b]} in its {nm}", "F2 dignity & condition", "Z", z,
                 kind="flag")] = np.isin(sb, signs).astype(float)
    if z == "lahiri":
        nak = (lon[:, B["Mo"]] // (360 / 27)).astype(int)
        for i, nm in enumerate(NAKSHATRAS):
            f[_m(f"Z.{z}.Mo.nak.{i}", f"Moon in nakshatra {nm}", "F2 dignity & condition", "Z", z,
                 kind="flag")] = (nak == i).astype(float)
    su = lon[:, B["Su"]] % 30
    f[_m(f"Z.{z}.sankranti", "Sun within 1° of a sign boundary (sankranti)", "F10 sky events", "Z", z,
         kind="flag")] = ((su < 1) | (su > 29)).astype(float)
    return f


def block_A(sky) -> dict[str, np.ndarray]:
    f = {}
    pts = _points(sky)
    cusps = sky["cusps_placidus"]
    for ai, (ang, ci) in enumerate(ANGLES.items()):
        c = cusps[:, ci]
        for j, b in enumerate(POINTS):
            x = pts[:, j]
            before = (c - x) % 360
            after = (x - c) % 360
            nm = BODY_NAMES[b]
            f[_m(f"A.{b}.{ang}.before", f"{nm} applying to {ANGLE_TEAM[ang]} (0–10° before the angle)",
                 "F4 angles", "A")] = np.where((before > 0) & (before <= 10), np.exp(-before / ANGLE_DECAY), 0.0)
            f[_m(f"A.{b}.{ang}.after", f"{nm} just past {ANGLE_TEAM[ang]} (0–10° inside)",
                 "F4 angles", "A")] = np.where(after <= 10, np.exp(-after / ANGLE_DECAY), 0.0)
            ax = ephem.antiscion(x)
            d = _sep(ax, c)
            f[_m(f"A.{b}.anti.{ang}", f"antiscion of {nm} on {ANGLE_TEAM[ang]}", "F4 angles", "A", "tropical")] = \
                np.exp(-0.5 * (d / 2.0) ** 2)
    return f


def _cusps(sky, system, z):
    ay = 0.0 if z == "tropical" else sky["ayan_lahiri"][:, None]
    if system in ("placidus", "regiomontanus", "campanus"):
        return ephem.norm360(sky[f"cusps_{system}"] - ay)
    asc = ephem.norm360(sky["asc"][:, None] - ay)
    if system == "equal":
        return ephem.norm360(asc + 30 * np.arange(12)[None, :])
    return ephem.norm360(np.floor(asc / 30) * 30 + 30 * np.arange(12)[None, :])


def _house_index(x, cusps):
    """Vectorised 1-based house of longitude x (n,) given cusps (n, 12)."""
    rel = (x[:, None] - cusps) % 360
    span = (np.roll(cusps, -1, axis=1) - cusps) % 360
    inside = rel < span
    return np.where(inside.any(1), inside.argmax(1) + 1, 12)


def block_H(sky, system: str, z: str, occupancy: bool) -> dict[str, np.ndarray]:
    f = {}
    cusps = _cusps(sky, system, z)
    ay = 0.0 if z == "tropical" else sky["ayan_lahiri"][:, None]
    pts = ephem.norm360(_points(sky) - ay)
    hs = np.column_stack([_house_index(pts[:, j], cusps) for j in range(pts.shape[1])])
    sysname = system.replace("_", " ").title()
    zn = "" if not occupancy or system != "whole_sign" else f", {z}"
    struct = f"{system}/{z}"
    if occupancy:
        tag = f"H.{system}" + (f".{z}" if system == "whole_sign" else "")
        st = system if system != "whole_sign" else struct
        for j, b in enumerate(POINTS):
            for h in range(1, 13):
                f[_m(f"{tag}.{b}.house{h}", f"{BODY_NAMES[b]} in the {_ord(h)} house ({sysname}{zn})",
                     "F4 houses", "H", st, kind="flag")] = (hs[:, j] == h).astype(float)
    # Lordship of the four team houses (depends on zodiac through the cusp sign)
    csign = (cusps // 30).astype(int) % 12
    ruler_idx = np.array([B[r] for r in RULER])
    lord = {h: ruler_idx[csign[:, h - 1]] for h in (1, 10, 7, 4)}
    tag = f"L.{system}.{z}"
    lon = pts[:, :len(BODIES)]
    for h in (1, 10, 7, 4):
        lh = hs[np.arange(len(hs)), lord[h]]
        for hh in range(1, 13):
            f[_m(f"{tag}.L{h}.house{hh}", f"lord of the {_ord(h)} ({_team(h)}) in the {_ord(hh)} house ({sysname}, {z})",
                 "F5 lordship", "H", struct, kind="flag")] = (lh == hh).astype(float)
        llon = lon[np.arange(len(lon)), lord[h]]
        for ang, ci in ANGLES.items():
            c = cusps[:, ci]
            before, after = (c - llon) % 360, (llon - c) % 360
            f[_m(f"{tag}.L{h}.{ang}.before", f"lord of the {_ord(h)} ({_team(h)}) applying to {ANGLE_TEAM[ang]} ({z})",
                 "F5 lordship", "H", struct)] = np.where((before > 0) & (before <= 10), np.exp(-before / ANGLE_DECAY), 0.0)
            f[_m(f"{tag}.L{h}.{ang}.after", f"lord of the {_ord(h)} ({_team(h)}) just inside {ANGLE_TEAM[ang]} ({z})",
                 "F5 lordship", "H", struct)] = np.where(after <= 10, np.exp(-after / ANGLE_DECAY), 0.0)
    # Moon's last applying aspect within 5 degrees of its travel (Frawley's window), by team lord
    last = _moon_last(sky, z)
    for role in ("L1", "L10", "L7", "L4"):
        h = int(role[1:])
        f[_m(f"{tag}.moonlast.{role}", f"Moon's last applying aspect (within 5°) is to the lord of the {_ord(h)} ({_team(h)})",
             "F6 Moon process", "H", struct, kind="flag")] = (last == lord[h]).astype(float)
    # Chokoisky-style victory-house malefic balance
    mal = [B[p] for p in ("Sa", "Ma", "Su", "Ra")]
    t1 = np.isin(hs[:, mal], [1, 3, 6, 10, 11]).sum(1)
    t2 = np.isin(hs[:, mal], [7, 9, 12, 4, 5]).sum(1)
    f[_m(f"{tag}.victory_malefics", f"malefics in team1's victory houses minus team2's ({sysname}, {z})",
         "F5 lordship", "H", struct, kind="continuous")] = (t1 - t2).astype(float)
    return f


def _moon_last(sky, z):
    lon = _lon(sky, z)
    spd = sky["bspd"]
    mo, ms = lon[:, B["Mo"]], spd[:, B["Mo"]]
    limit = np.minimum(5.0, 30 - mo % 30)
    best_t = np.full(len(mo), -1.0)
    best_p = np.full(len(mo), -1)
    for p in ["Su", "Me", "Ve", "Ma", "Ju", "Sa"]:
        rel = ms - spd[:, B[p]]
        for ang in PTOLEMAIC:
            for s in (1, -1):
                gap = (lon[:, B[p]] + s * ang - mo) % 360
                t = gap * ms / rel
                ok = (t <= limit) & (t > best_t)
                best_t = np.where(ok, t, best_t)
                best_p = np.where(ok, B[p], best_p)
    return best_p


def _ord(h):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(h, f"{h}th")


def _team(h):
    return "team1" if h in (1, 10) else "team2" if h in (7, 4) else "neutral"


def build(sky: dict) -> pd.DataFrame:
    f = {}
    f.update(block_S(sky))
    for z in ZODIACS:
        f.update(block_Z(sky, z))
    f.update(block_A(sky))
    for system in HOUSES:
        for z in ZODIACS:
            occ = (z == "tropical") or system == "whole_sign"     # occupancy is zodiac-free otherwise
            f.update(block_H(sky, system, z, occupancy=occ))
    df = pd.DataFrame({k: v.astype(np.float32) for k, v in f.items()})
    df.attrs["lattice_version"] = LATTICE_VERSION
    return df


def meta_frame() -> pd.DataFrame:
    return pd.DataFrame.from_dict(META, orient="index")
