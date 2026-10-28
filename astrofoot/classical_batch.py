"""Run Engines 1-3 over every match of a sky (FAV frame: the favourite owns the Lagna)."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import sky as skymod
from .config import WORK
from .engines import chokoisky, frawley, rao

WIN = {"fav": 1, "draw": 0, "dog": -1, "disabled": 0}


def _run(args):
    sky, idx, fav_names, dog_names, equal = args
    rows = []
    for k, i in enumerate(idx):
        rc = skymod.rc_at(sky, i)
        r = rao.analyse(rc, draw_possible=True)
        c = chokoisky.analyse(rc, fav_names[k], dog_names[k], draw_possible=True)
        f = frawley.analyse(rc, draw_possible=True, equal_odds=bool(equal[k]))
        row = {
            "rao_win": WIN[r.winner], "rao_net": r.net,
            "chok_win": WIN[c.winner], "chok_net": c.net,
            "fraw_win": WIN[f.winner], "fraw_net": f.net, "fraw_disabled": f.winner == "disabled",
            "fraw_late_goal": bool(f.features.get("late_goal", False)),
            "chok_d9": bool(c.features.get("d9_cusp_planet")), "chok_sublord": c.features.get("sublord_diff", 0.0),
        }
        for e in (r, c, f):
            for key, val in e.doctrine_flags().items():
                row[f"doc.{key}"] = val
        rows.append(row)
    return rows


def run(m: pd.DataFrame, sky: dict, workers: int = 4) -> pd.DataFrame:
    fav = np.where(m.fav_is_home, m.home, m.away)
    dog = np.where(m.fav_is_home, m.away, m.home)
    parts = np.array_split(np.arange(len(m)), workers * 16)
    small = {k: v for k, v in sky.items()}
    with ProcessPoolExecutor(workers) as ex:
        res = ex.map(_run, [(small, ix, fav[ix], dog[ix], m.equal_odds.to_numpy()[ix]) for ix in parts])
        rows = [r for chunk in res for r in chunk]
    out = pd.DataFrame(rows, index=m.index)
    doc = [c for c in out.columns if c.startswith("doc.")]
    out[doc] = out[doc].fillna(0.0).astype(np.float32)
    out.to_parquet(WORK / "engines_real.parquet")
    return out
