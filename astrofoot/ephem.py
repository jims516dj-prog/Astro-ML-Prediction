"""Swiss Ephemeris wrapper.

Uses the built-in Moshier ephemeris (no data files; sub-arcsecond for the planets used,
which is far below any orb in this project). One `raw_chart` call yields everything both
the classical engines and the lattice need; zodiac/house variants are derived from it
without further ephemeris calls:

  * sidereal longitude  = tropical - ayanamsha   (Lahiri or KP)
  * quadrant cusps (Placidus/Regiomontanus/Campanus) are zodiac-independent points, so the
    sidereal cusp is the tropical cusp - ayanamsha
  * Whole Sign / Equal cusps are built from the Ascendant in the chosen zodiac
Above ~66 deg latitude Placidus is undefined; Swiss Ephemeris falls back to Porphyry and the
chart is flagged `polar`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import swisseph as swe

from .tables import BODIES, CHALDEAN

FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED
_IDS = {"Su": swe.SUN, "Mo": swe.MOON, "Me": swe.MERCURY, "Ve": swe.VENUS, "Ma": swe.MARS,
        "Ju": swe.JUPITER, "Sa": swe.SATURN, "Ur": swe.URANUS, "Ne": swe.NEPTUNE,
        "Pl": swe.PLUTO, "Ra": swe.TRUE_NODE}
QUADRANT_SYSTEMS = {"placidus": b"P", "regiomontanus": b"R", "campanus": b"C"}
HOUSE_SYSTEMS = ["placidus", "whole_sign", "equal", "regiomontanus", "campanus"]


def jd_utc(dt: datetime) -> float:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    h = dt.hour + dt.minute / 60 + dt.second / 3600
    return swe.julday(dt.year, dt.month, dt.day, h, swe.GREG_CAL)


def norm360(x):
    return np.mod(x, 360.0)


def angdiff(a, b):
    """Signed shortest arc a - b in (-180, 180]."""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def ayanamsha(jd: float, mode: str) -> float:
    swe.set_sid_mode({"lahiri": swe.SIDM_LAHIRI, "kp": swe.SIDM_KRISHNAMURTI}[mode])
    return swe.get_ayanamsa_ut(jd)


def _planetary_hour(jd: float, lat: float, lon: float):
    geo = (lon, lat, 0.0)
    fl = swe.FLG_MOSEPH

    def nxt(t, what):
        res, tret = swe.rise_trans(t, swe.SUN, what, geo, 0, 0, fl)
        return tret[0] if res == 0 else None

    rise1 = nxt(jd - 1.0, swe.CALC_RISE)
    if rise1 is None:          # polar day/night: no planetary hours
        return None, None
    if rise1 > jd:
        rise1 = nxt(jd - 2.0, swe.CALC_RISE)
        if rise1 is None or rise1 > jd:
            return None, None
    set1 = nxt(rise1, swe.CALC_SET)
    rise2 = nxt(set1, swe.CALC_RISE) if set1 else None
    if set1 is None or rise2 is None:
        return None, None
    day_lord_idx = {6: 3, 0: 6, 1: 2, 2: 5, 3: 1, 4: 4, 5: 0}  # swe weekday(Mon=0) -> CHALDEAN idx
    wd = swe.day_of_week(rise1 + lon / 360.0)
    start = day_lord_idx[wd]
    if jd < set1:
        hour = int((jd - rise1) / ((set1 - rise1) / 12))
    else:
        hour = 12 + int((jd - set1) / ((rise2 - set1) / 12))
    hour = min(max(hour, 0), 23)
    # minutes from the nearer of sunrise/sunset (sandhi guardrail)
    sun_edge_min = min(abs(jd - rise1), abs(jd - set1), abs(rise2 - jd)) * 1440
    return CHALDEAN[(start + hour) % 7], sun_edge_min


def raw_chart(jd: float, lat: float, lon: float, with_hours: bool = True) -> dict:
    out: dict = {"jd": jd, "lat": lat, "lon": lon}
    lons, lats, spds, decs = [], [], [], []
    for b in BODIES:
        xx, _ = swe.calc_ut(jd, _IDS[b], FLAGS)
        eq, _ = swe.calc_ut(jd, _IDS[b], FLAGS | swe.FLG_EQUATORIAL)
        lons.append(xx[0]); lats.append(xx[1]); spds.append(xx[3]); decs.append(eq[1])
    out["blon"] = np.array(lons)
    out["blat"] = np.array(lats)
    out["bspd"] = np.array(spds)
    out["bdec"] = np.array(decs)
    out["ayan_lahiri"] = ayanamsha(jd, "lahiri")
    out["ayan_kp"] = ayanamsha(jd, "kp")
    polar = False
    for name, code in QUADRANT_SYSTEMS.items():
        try:
            cusps, ascmc = swe.houses_ex(jd, lat, lon, code)
        except swe.Error:          # Placidus is undefined inside the polar circle
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b"O")
            polar = True
        out[f"cusps_{name}"] = np.array(cusps[:12])
        if name == "placidus":
            out["asc"], out["mc"], out["armc"] = ascmc[0], ascmc[1], ascmc[2]
    out["polar"] = polar
    if with_hours:
        out["hour_lord"], out["sun_edge_min"] = _planetary_hour(jd, lat, lon)
    return out


def cusps_for(rc: dict, system: str, ayan: float) -> np.ndarray:
    """12 cusps in the zodiac defined by `ayan` (0 = tropical)."""
    if system in QUADRANT_SYSTEMS:
        return norm360(rc[f"cusps_{system}"] - ayan)
    asc = norm360(rc["asc"] - ayan)
    if system == "whole_sign":
        return norm360(np.floor(asc / 30) * 30 + 30 * np.arange(12))
    if system == "equal":
        return norm360(asc + 30 * np.arange(12))
    raise ValueError(system)


def house_of(x: float, cusps: np.ndarray) -> int:
    """1-based house containing longitude x."""
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        span = (b - a) % 360
        if (x - a) % 360 < span:
            return i + 1
    return 12


def sign_of(x) -> int:
    return int(np.floor(norm360(x) / 30)) % 12


def nakshatra(x_sid: float) -> tuple[int, int]:
    """(nakshatra index 0-26, pada index 0-107)."""
    x = float(norm360(x_sid))
    return int(x // (360 / 27)), int(x // (360 / 108))


def d9(x_sid):
    """Navamsha longitude with exact degrees (each 3deg20' maps onto a 30deg sign)."""
    return norm360(np.asarray(x_sid) * 9.0)


def antiscion(x):
    return norm360(180.0 - np.asarray(x))


def contra_antiscion(x):
    return norm360(360.0 - np.asarray(x))


def kp_sublord(x_kp: float) -> tuple[str, str]:
    """(star lord, sub lord) of a KP-sidereal longitude."""
    from .tables import DASHA_ORDER, DASHA_YEARS
    span = 360 / 27
    x = float(norm360(x_kp))
    n = int(x // span)
    star = DASHA_ORDER[n % 9]
    within = x - n * span
    i0 = DASHA_ORDER.index(star)
    acc = 0.0
    for k in range(9):
        p = DASHA_ORDER[(i0 + k) % 9]
        acc += span * DASHA_YEARS[p] / 120
        if within < acc:
            return star, p
    return star, DASHA_ORDER[(i0 + 8) % 9]


def eclipses(jd_from: float, jd_to: float) -> list[tuple[float, str, float]]:
    """(jd of maximum, 'solar'|'lunar', tropical Sun longitude) between the bounds."""
    out = []
    for kind in ("solar", "lunar"):
        t = jd_from
        while t < jd_to:
            if kind == "solar":
                _, tret = swe.sol_eclipse_when_glob(t, swe.FLG_MOSEPH, 0, False)
            else:
                _, tret = swe.lun_eclipse_when(t, swe.FLG_MOSEPH, 0, False)
            tm = tret[0]
            if tm > jd_to:
                break
            sun, _ = swe.calc_ut(tm, swe.SUN, swe.FLG_MOSEPH)
            out.append((tm, kind, sun[0]))
            t = tm + 20
    return sorted(out)
