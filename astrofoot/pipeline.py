"""Training & validation pipeline (spec §12.5 - §12.8).

Everything that selects anything (team frame, L1 strength, screened features) happens
*inside* each walk-forward fold using only that fold's training seasons, so the same code
can be re-run unchanged on placebo skies.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import dataset, lattice, models
from . import sky as skymod
from .config import FIRST_TEST_SEASON, LATTICE_VERSION, LIVING, MODELS, VAULT_START, WORK

TEST_SEASONS = ["2020/21", "2021/22", "2022/23", "2023/24", "2024/25"]     # L-2026.1 (pre-vault) evaluation
# The books put the favourite in the 1st house, and their testimonies (block C) are defined that way;
# L-2026.1 found no advantage for the HOME frame, so the living engine uses FAV only.
FRAMES = ["FAV"] if LIVING else ["FAV", "HOME"]
SCREEN_K = 300
LAMBDA_GRID = [0.9, 0.6, 0.4, 0.25, 0.15, 0.1]
L2 = 1e-4
INNER_VAL_SEASONS = 2


@dataclass
class Data:
    m: pd.DataFrame
    X: np.ndarray
    cols: list[str]
    frames: dict
    controls: dict
    vault: np.ndarray
    season: np.ndarray
    day: np.ndarray
    test_seasons: list


def load(X: pd.DataFrame | None = None, sky_kind="real", seed=0, E: pd.DataFrame | None = None,
         classical: bool = True) -> Data:
    """Matches + feature matrix. X: sky lattice (built if None). E: Engines 1-3 output for the same sky
    (the real sky's cached run if None); with `classical`, the books' testimonies join the features."""
    from . import classical_batch
    m = pd.read_parquet(WORK / "matches.parquet")
    if X is None:
        X = lattice.build(skymod.compute_sky(m, sky_kind, seed))
    if classical:
        if E is None:
            E = pd.read_parquet(WORK / "engines_real.parquet")
        if len(E) != len(m):
            raise SystemExit("engines_real.parquet is out of date: run scripts/research.py prepare")
        X = pd.concat([X.reset_index(drop=True), classical_batch.features(E).reset_index(drop=True)], axis=1)
    keep = X.std().to_numpy() > 1e-6
    cols = list(X.columns[keep])
    Xn = X.to_numpy(np.float32)[:, keep]
    del X
    frames = {f: dataset.frame_view(m, f) for f in FRAMES + ["COIN"]}
    controls = {f: models.control_matrix(m, frames[f]) for f in frames}
    if LIVING:
        vault = np.zeros(len(m), bool)
        counts = m.season.value_counts()
        tests = sorted(s for s in counts.index if s >= FIRST_TEST_SEASON and counts[s] >= 300)
    else:
        vault = (m.kickoff_utc >= pd.Timestamp(VAULT_START, tz="UTC")).to_numpy()
        tests = TEST_SEASONS
    return Data(m, Xn, cols, frames, controls, vault, m.season.to_numpy(),
                m.kickoff_utc.dt.strftime("%Y-%m-%d").to_numpy(), tests)


def _m0(d: Data, frame: str, tr: np.ndarray):
    y = d.frames[frame].y.to_numpy()
    mod = models.M0().fit(d.controls[frame][tr], y[tr])
    return mod, np.log(np.clip(mod.predict(d.controls[frame]), 1e-9, 1)), y


def _fit_path(X, y, logP0, tr, va, cols_idx):
    """Fit an L1 path on `tr`, return [(frac, model, per-row validation log loss)]."""
    Xtr = X[np.ix_(tr, cols_idx)]
    sv = models.score_vector(Xtr, y[tr], logP0[tr])
    lam_max = float(sv.max())
    out, warm = [], None
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd = np.maximum(sd, models.SD_FLOOR)
    for frac in LAMBDA_GRID:
        mod = models.OffsetSoftmax(l1=lam_max * frac, l2=L2).fit(Xtr, y[tr], logP0[tr], warm=warm,
                                                                 standardise=(mu, sd))
        warm = mod.theta
        vl = models.logloss(mod.predict(X[np.ix_(va, cols_idx)], logP0[va]), y[va]) if va is not None else None
        out.append((frac, mod, vl))
    return out, lam_max


def _screen(X, y, logP0, tr, k=SCREEN_K, cols=None):
    sv = models.score_vector(X[tr] if cols is None else X[np.ix_(tr, cols)], y[tr], logP0[tr])
    idx = np.argsort(-sv)[:k]
    return idx if cols is None else np.asarray(cols)[idx]


def select_and_fit(d: Data, X: np.ndarray, tr: np.ndarray, frames=FRAMES):
    """Inner validation picks the frame and lambda; refit on all of tr.

    Validation spans the last INNER_VAL_SEASONS training seasons. One season is not enough:
    planetary configurations cluster in calendar time (Mars spends ~6 weeks in a sign every ~2
    years), so a single validation season can contain zero exposures to a real effect and the
    selector then always chooses the null model (found by the planted-signal self-test).
    """
    seasons = sorted(set(d.season[tr]))
    va = tr & np.isin(d.season, seasons[-INNER_VAL_SEASONS:])
    itr = tr & ~va
    days = d.day[va]
    cands = []
    for fr in frames:
        _, lp, y = _m0(d, fr, itr)
        base = models.logloss(np.exp(lp[va]), y[va])
        cols = _screen(X, y, lp, itr)
        path, _ = _fit_path(X, y, lp, np.where(itr)[0], np.where(va)[0], cols)
        for frac, mod, vl in path:
            g = pd.Series(base - vl).groupby(days).sum()        # matchday-clustered gain
            n = len(vl)
            cands.append({"frame": fr, "frac": frac, "gain": float(g.sum() / n),
                          "se": float(g.std(ddof=1) * np.sqrt(len(g)) / n)})
    # One-standard-error rule: the sparsest model within 1 SE of the best, and only if its own
    # gain over the market model exceeds 1 SE (otherwise the null model).
    top = max(cands, key=lambda c: c["gain"])
    ok = [c for c in cands if c["gain"] >= top["gain"] - top["se"]]
    best = dict(max(ok, key=lambda c: (c["frac"], c["frame"] == top["frame"])))
    if best["gain"] <= best["se"]:
        best["frac"] = None
    fr = best["frame"]
    m0, lp, y = _m0(d, fr, tr)
    if best["frac"] is None:
        return {"frame": fr, "frac": None, "m0": m0, "model": None, "cols": np.array([], int),
                "logP0": lp, "y": y, "val_gain": best["gain"]}
    cols = _screen(X, y, lp, tr)
    Xtr = X[np.ix_(tr, cols)]
    lam_max = float(models.score_vector(Xtr, y[tr], lp[tr]).max())
    mod = models.OffsetSoftmax(l1=lam_max * best["frac"], l2=L2).fit(Xtr, y[tr], lp[tr])
    return {"frame": fr, "frac": best["frac"], "m0": m0, "model": mod, "cols": cols, "logP0": lp, "y": y,
            "val_gain": best["gain"]}


def walk_forward(d: Data, X: np.ndarray | None = None, frames=FRAMES, label="engine4") -> pd.DataFrame:
    X = d.X if X is None else X
    rows = []
    for s in d.test_seasons:
        tr = (d.season < s) & ~d.vault
        te = (d.season == s) & ~d.vault
        fit = select_and_fit(d, X, tr, frames)
        y, lp = fit["y"], fit["logP0"]
        P0 = np.exp(lp[te])
        P0 /= P0.sum(1, keepdims=True)
        P2 = P0 if fit["model"] is None else fit["model"].predict(X[np.ix_(te, fit["cols"])], lp[te])
        mk = models.market_only(d.frames[fit["frame"]])[te]
        rows.append(pd.DataFrame({
            "idx": np.where(te)[0], "season": s, "day": d.day[te], "frame": fit["frame"], "y": y[te],
            "P0": list(P0), "P2": list(P2), "PM": list(mk),
            "n_active": int(fit["model"].active.sum()) if fit["model"] is not None else 0,
            "frac": fit["frac"] if fit["frac"] is not None else np.nan, "val_gain": fit["val_gain"],
        }))
    return pd.concat(rows, ignore_index=True)


def summarise(oof: pd.DataFrame) -> dict:
    y = oof.y.to_numpy()
    P0, P2, PM = (np.stack(oof[c].to_numpy()) for c in ("P0", "P2", "PM"))
    s0, s2, sm = models.scores(P0, y), models.scores(P2, y), models.scores(PM, y)
    d_rps = models.block_bootstrap_delta(models.rps(P2, y), models.rps(P0, y), oof.day.to_numpy())
    d_ll = models.block_bootstrap_delta(models.logloss(P2, y), models.logloss(P0, y), oof.day.to_numpy())
    per = oof.groupby("season").agg(frame=("frame", "first"), n_active=("n_active", "first"),
                                    frac=("frac", "first")).reset_index().to_dict("records")
    return {"market": sm, "m0": s0, "engine4": s2, "delta_rps_vs_m0": d_rps, "delta_logloss_vs_m0": d_ll,
            "ece_engine4": models.ece(P2, y), "ece_m0": models.ece(P0, y), "folds": per}


# ------------------------------------------------------------- univariate screens & tribunal
def score_z(X: np.ndarray, y: np.ndarray, logP0: np.ndarray) -> np.ndarray:
    """Score-test z for every column on the team1-vs-team2 axis (vectorised)."""
    P = np.exp(logP0)
    c = ((y == 0).astype(float) - (y == 2) - (P[:, 0] - P[:, 2])).astype(np.float32)
    v = (P[:, 0] + P[:, 2] - (P[:, 0] - P[:, 2]) ** 2).astype(np.float32)
    mu = X.mean(0, dtype=np.float64)
    U = X.T @ c - mu * c.sum()
    # sum v (x - mu)^2 = sum v x^2 - 2 mu sum v x + mu^2 sum v
    I = (X * X).T @ v - 2 * mu * (X.T @ v) + mu ** 2 * v.sum()
    return U / np.sqrt(np.maximum(I, 1e-12))


def tribunal(d: Data, E: pd.DataFrame) -> pd.DataFrame:
    """Doctrine Tribunal: every classical testimony as a pre-registered hypothesis (FAV frame)."""
    pre = ~d.vault
    m0, lp, y = _m0(d, "FAV", pre)
    rows = []
    for col in [c for c in E.columns if c.startswith("doc.")]:
        x = E[col].to_numpy(float)
        if (x[pre] != 0).sum() < 30:
            continue
        r = models.univariate(x[pre], y[pre], lp[pre])
        rv = models.univariate(x[d.vault], y[d.vault], lp[d.vault]) if (x[d.vault] != 0).sum() >= 30 else None
        act = pre & (x != 0)
        pick_t1 = x[act] > 0
        won = np.where(pick_t1, y[act] == 0, y[act] == 2)
        P = np.exp(lp[act])
        exp_hit = np.where(pick_t1, P[:, 0], P[:, 2])
        rows.append({"doctrine": col[4:], "book": col[4:].split(".")[0], **r,
                     "hit_rate": float(won.mean()), "market_expected": float(exp_hit.mean()),
                     "vault_beta": rv["beta"] if rv else None, "vault_p": rv["p"] if rv else None,
                     "vault_n": rv["n_active"] if rv else 0})
    t = pd.DataFrame(rows)
    t["p_holm"] = models.holm(t.p.to_numpy())
    ci = 1.96 * t.se
    t["verdict"] = np.select(
        [(t.p_holm < 0.05) & (t.beta > 0), (t.p_holm < 0.05) & (t.beta < 0), ci > 0.25],
        ["supported", "reversed", "insufficient data"], "not supported")
    return t.sort_values("p")


def classical_walk_forward(d: Data, E: pd.DataFrame) -> pd.DataFrame:
    """M1: how much the three books add beyond the market (FAV frame, ridge)."""
    F = pd.DataFrame({
        "rao_fav": (E.rao_win == 1), "rao_dog": (E.rao_win == -1), "rao_net": E.rao_net,
        "chok_fav": (E.chok_win == 1), "chok_dog": (E.chok_win == -1), "chok_net": E.chok_net.clip(-40, 40),
        "fraw_fav": (E.fraw_win == 1), "fraw_dog": (E.fraw_win == -1), "fraw_net": E.fraw_net,
        "chok_d9": E.chok_d9, "fraw_late": E.fraw_late_goal,
    }).astype(np.float32).to_numpy()
    rows = []
    for s in d.test_seasons:
        tr = (d.season < s) & ~d.vault
        te = (d.season == s) & ~d.vault
        m0, lp, y = _m0(d, "FAV", tr)
        mod = models.OffsetSoftmax(l1=0.0, l2=1e-2).fit(F[tr], y[tr], lp[tr])
        P0 = np.exp(lp[te]); P0 /= P0.sum(1, keepdims=True)
        rows.append(pd.DataFrame({"idx": np.where(te)[0], "season": s, "day": d.day[te], "frame": "FAV",
                                  "y": y[te], "P0": list(P0), "P2": list(mod.predict(F[te], lp[te])),
                                  "PM": list(models.market_only(d.frames["FAV"])[te]),
                                  "n_active": F.shape[1], "frac": np.nan, "val_gain": np.nan}))
    return pd.concat(rows, ignore_index=True)


def engine_accuracy(d: Data, E: pd.DataFrame) -> dict:
    y = d.frames["FAV"].y.to_numpy()
    act = np.select([y == 0, y == 1], [1, 0], -1)
    pre = ~d.vault
    out = {}
    for k, nm in (("rao", "Rao"), ("chok", "Chokoisky"), ("fraw", "Frawley")):
        w = E[f"{k}_win"].to_numpy()
        ok = pre & ~(E.get("fraw_disabled", False).to_numpy() if k == "fraw" else np.zeros(len(w), bool))
        out[nm] = {"accuracy": float((w[ok] == act[ok]).mean()), "n": int(ok.sum()),
                   "picks_favourite": float((w[ok] == 1).mean()), "picks_draw": float((w[ok] == 0).mean())}
    out["Always favourite"] = {"accuracy": float((act[pre] == 1).mean()), "n": int(pre.sum()),
                               "picks_favourite": 1.0, "picks_draw": 0.0}
    P = models.market_only(d.frames["FAV"])[pre]
    out["Market (most likely outcome)"] = {"accuracy": float((P.argmax(1) == y[pre]).mean()), "n": int(pre.sum()),
                                           "picks_favourite": float((P.argmax(1) == 0).mean()),
                                           "picks_draw": float((P.argmax(1) == 1).mean())}
    return out


def save_json(obj, name):
    p = MODELS / name
    p.write_text(json.dumps(obj, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    return p


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")
