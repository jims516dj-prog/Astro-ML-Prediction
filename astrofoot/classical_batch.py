"""Run Engines 1-3 over every match of a sky (FAV frame: the favourite owns the Lagna)."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import sky as skymod
from .config import WORK
from .engines import chokoisky, frawley, rao

WIN = {"fav": 1, "draw": 0, "dog": -1, "disabled": 0}


def engine_row(rc: dict, fav: str, dog: str, equal_odds: bool) -> dict:
    """Engines 1-3 on one chart, in the standard research setting (league rules, no founding charts or
    captains): exactly what Engine 4 is trained on, used both in batch and for single live matches."""
    r = rao.analyse(rc, draw_possible=True)
    c = chokoisky.analyse(rc, fav, dog, draw_possible=True)
    f = frawley.analyse(rc, draw_possible=True, equal_odds=bool(equal_odds))
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
    return row


def _run(args):
    sky, idx, fav_names, dog_names, equal = args
    return [engine_row(skymod.rc_at(sky, i), fav_names[k], dog_names[k], equal[k]) for k, i in enumerate(idx)]


def run(m: pd.DataFrame, sky: dict, workers: int | None = None, out_path=None) -> pd.DataFrame:
    """Engines 1-3 over every match of a sky. The real sky's output is cached in engines_real.parquet;
    placebo skies pass out_path=False so nothing is written."""
    import os
    workers = workers or max(1, os.cpu_count() or 1)
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
    if out_path is not False:
        out.to_parquet(out_path or (WORK / "engines_real.parquet"))
    return out


def features(E: pd.DataFrame) -> pd.DataFrame:
    """The three books as Engine 4 inputs (favourite frame, +1 = for the favourite, -1 = for the underdog).

    Every testimony type (doctrine) becomes a signed flag, and each engine's verdict and net score a number,
    so the learner can find which classical patterns - alone, or alongside the sky primitives - carry signal.
    """
    from . import lattice
    f = {}
    for col in [c for c in E.columns if c.startswith("doc.")]:
        key = col[4:]
        name = f"C.{key}"
        lattice.META[name] = {"desc": f"{key.split('.')[0].capitalize()} testimony '{'.'.join(key.split('.')[1:])}' "
                                      f"(+ favours the favourite)", "family": "F11 classical testimonies",
                              "block": "C", "structure": key.split(".")[0], "kind": "signed"}
        f[name] = E[col].to_numpy(np.float32)
    for eng, label in (("rao", "Rao"), ("chok", "Chokoisky"), ("fraw", "Frawley")):
        for side, v in (("fav", 1), ("dog", -1), ("draw", 0)):
            name = f"C.{eng}.verdict.{side}"
            lattice.META[name] = {"desc": f"{label}'s verdict: {'draw' if side == 'draw' else 'the ' + ('favourite' if side == 'fav' else 'underdog')}",
                                  "family": "F11 classical verdicts", "block": "C", "structure": eng, "kind": "flag"}
            f[name] = (E[f"{eng}_win"].to_numpy() == v).astype(np.float32)
        name = f"C.{eng}.net"
        lattice.META[name] = {"desc": f"{label}'s net score (favourite minus underdog)", "family": "F11 classical verdicts",
                              "block": "C", "structure": eng, "kind": "continuous"}
        f[name] = np.clip(E[f"{eng}_net"].to_numpy(np.float32), -40, 40) / 10
    for col, desc in (("chok_d9", "Chokoisky: a planet on a D9 (navamsha) cusp"),
                      ("fraw_late_goal", "Frawley: Moon's final aspect late in its range (late goal)")):
        lattice.META[f"C.{col}"] = {"desc": desc, "family": "F11 classical verdicts", "block": "C",
                                    "structure": col.split("_")[0], "kind": "flag"}
        f[f"C.{col}"] = E[col].astype(np.float32).to_numpy()
    lattice.META["C.chok_sublord"] = {"desc": "Chokoisky: KP sublord difference (cusp 1 minus cusp 7)",
                                      "family": "F11 classical verdicts", "block": "C", "structure": "chokoisky",
                                      "kind": "continuous"}
    f["C.chok_sublord"] = np.clip(E["chok_sublord"].fillna(0).to_numpy(np.float32), -40, 40) / 10
    return pd.DataFrame(f, index=E.index)


def single_row(rc: dict, fav: str, dog: str, equal_odds: bool) -> pd.DataFrame:
    """Engine 4's classical feature row for one match (same computation as the training batch)."""
    E = pd.DataFrame([engine_row(rc, fav, dog, equal_odds)])
    doc = [c for c in E.columns if c.startswith("doc.")]
    E[doc] = E[doc].fillna(0.0)
    return features(E)
