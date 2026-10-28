"""Raw sky arrays for every match: the real sky and placebo skies.

A *sky* is one ephemeris snapshot per match. Placebo skies shift the moment or the place
(§12.6.4 of the spec) while every non-astrological column stays untouched:

  real        kickoff time at the venue
  time_shift  same date & venue, kickoff moved by a random +/-2..10 h  (scrambles angles, Moon)
  date_shift  same clock time & venue, date moved by a random +/-7..56 days (scrambles planets)
  place_shift same moment, venue swapped with another match's venue    (scrambles angles only)
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from . import ephem
from .config import WORK
from .tables import BODIES, CHALDEAN

SKY_DIR = WORK / "skies"
SKY_DIR.mkdir(exist_ok=True)


def _chunk(args):
    jds, lats, lons = args
    n = len(jds)
    out = {
        "blon": np.empty((n, len(BODIES))), "bspd": np.empty((n, len(BODIES))),
        "bdec": np.empty((n, len(BODIES))), "ayan_lahiri": np.empty(n), "ayan_kp": np.empty(n),
        "asc": np.empty(n), "mc": np.empty(n), "cusps_placidus": np.empty((n, 12)),
        "cusps_regiomontanus": np.empty((n, 12)), "cusps_campanus": np.empty((n, 12)),
        "hour_lord": np.full(n, -1, np.int8), "sun_edge_min": np.full(n, np.nan), "polar": np.zeros(n, bool),
    }
    for i in range(n):
        rc = ephem.raw_chart(jds[i], lats[i], lons[i])
        for k in ("blon", "bspd", "bdec", "cusps_placidus", "cusps_regiomontanus", "cusps_campanus"):
            out[k][i] = rc[k]
        for k in ("ayan_lahiri", "ayan_kp", "asc", "mc", "polar"):
            out[k][i] = rc[k]
        if rc["hour_lord"] is not None:
            out["hour_lord"][i] = CHALDEAN.index(rc["hour_lord"])
            out["sun_edge_min"][i] = rc["sun_edge_min"]
    return out


def placebo_moments(m: pd.DataFrame, kind: str, seed: int):
    rng = np.random.default_rng(seed)
    jd = m.kickoff_utc.map(lambda t: ephem.jd_utc(t.to_pydatetime())).to_numpy()
    lat, lon = m.lat.to_numpy(), m.lon.to_numpy()
    n = len(m)
    if kind == "real":
        return jd, lat, lon
    if kind == "time_shift":
        return jd + rng.choice([-1, 1], n) * rng.uniform(2, 10, n) / 24, lat, lon
    if kind == "date_shift":
        return jd + rng.choice([-1, 1], n) * rng.integers(7, 57, n), lat, lon
    if kind == "place_shift":
        perm = rng.permutation(n)
        return jd, lat[perm], lon[perm]
    raise ValueError(kind)


def sky_path(kind: str, seed: int) -> Path:
    return SKY_DIR / (f"{kind}.npz" if kind == "real" else f"{kind}_{seed}.npz")


def compute_sky(m: pd.DataFrame, kind: str = "real", seed: int = 0, workers: int = 4) -> dict:
    p = sky_path(kind, seed)
    if p.exists():
        z = np.load(p)
        if len(z["asc"]) == len(m):
            return {k: z[k] for k in z.files}
    jd, lat, lon = placebo_moments(m, kind, seed)
    parts = np.array_split(np.arange(len(m)), workers * 8)
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(_chunk, [(jd[ix], lat[ix], lon[ix]) for ix in parts]))
    sky = {k: np.concatenate([r[k] for r in res]) for k in res[0]}
    sky["jd"] = jd
    sky["lat"] = lat
    np.savez_compressed(p, **sky)
    return sky


def rc_at(sky: dict, i: int) -> dict:
    """Rebuild a single raw-chart dict (as returned by ephem.raw_chart) from sky arrays."""
    rc = {k: sky[k][i] for k in ("blon", "bspd", "bdec", "cusps_placidus", "cusps_regiomontanus",
                                 "cusps_campanus")}
    rc.update({k: float(sky[k][i]) for k in ("ayan_lahiri", "ayan_kp", "asc", "mc", "jd")})
    rc["polar"] = bool(sky["polar"][i])
    hl = int(sky["hour_lord"][i])
    rc["hour_lord"] = CHALDEAN[hl] if hl >= 0 else None
    return rc
