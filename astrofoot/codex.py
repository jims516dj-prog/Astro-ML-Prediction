"""The Emergent Codex (spec §12.7): rules in astrological language with their evidence.

A rule starts life as a feature the final L1 model keeps. It is promoted to *Provisional*
only if it passes every filter of §12.6.5; *Established* additionally needs a clean vault
result and a season of prospective-ledger confirmation, which a fresh install cannot have.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import lattice, models
from .pipeline import SCREEN_K, L2, Data, _m0, _screen

FRAME_WORDS = {"FAV": ("the favourite", "the underdog"), "HOME": ("the home side", "the away side"),
               "COIN": ("team1", "team2")}


def statement(feature: str, frame: str, effect_pp: float) -> str:
    desc = lattice.META.get(feature, {}).get("desc", feature)
    t1, t2 = FRAME_WORDS.get(frame, ("team1", "team2"))
    desc = desc.replace("team1's", f"{t1}'s").replace("team2's", f"{t2}'s").replace("team1", t1).replace("team2", t2)
    direction = "rises" if effect_pp > 0 else "falls"
    return f"When {desc}, {t1}'s win probability {direction} {abs(effect_pp):.1f} pp relative to the market."


def orb_curve(feature: str, x: np.ndarray, y: np.ndarray, logP0: np.ndarray) -> list[dict] | None:
    """Empirical 'learned orb': team1 advantage beyond market by angular distance band."""
    meta = lattice.META.get(feature, {})
    if meta.get("kind") != "kernel":
        return None
    k = np.clip(x, 1e-12, 1)
    if feature.endswith((".before", ".after")):
        dist = -lattice.ANGLE_DECAY * np.log(k)
        dist[x == 0] = np.inf
    else:
        sigma = 4.0 if "combust" in feature else 2.0 if ".anti." in feature else lattice.ASPECT_SIGMA
        dist = sigma * np.sqrt(-2 * np.log(k))
    P = np.exp(logP0)
    resid = ((y == 0).astype(float) - (y == 2)) - (P[:, 0] - P[:, 2])
    edges = [0, 1, 2, 3, 4, 6, 8, 10]
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        msk = (dist >= a) & (dist < b)
        if msk.sum() >= 20:
            out.append({"band": f"{a}–{b}°", "edge_pp": float(resid[msk].mean() * 50), "n": int(msk.sum())})
    far = np.isfinite(dist) & (dist >= 10) | ~np.isfinite(dist)
    out.append({"band": "beyond", "edge_pp": float(resid[far].mean() * 50), "n": int(far.sum())})
    return out


def stability(d: Data, X, tr, frame, frac, features: list[int], n_sub=10, seed=0) -> dict[int, float]:
    rng = np.random.default_rng(seed)
    days = np.unique(d.day[tr])
    hits = {j: 0 for j in features}
    for _ in range(n_sub):
        keep_days = set(rng.choice(days, len(days) // 2, replace=False))
        sub = tr & np.isin(d.day, list(keep_days))
        _, lp, y = _m0(d, frame, sub)
        cols = _screen(X, y, lp, sub, k=SCREEN_K)
        Xs = X[np.ix_(sub, cols)]
        lam = float(models.score_vector(Xs, y[sub], lp[sub]).max()) * frac
        mod = models.OffsetSoftmax(l1=lam, l2=L2).fit(Xs, y[sub], lp[sub])
        act = set(np.asarray(cols)[mod.active])
        for j in features:
            hits[j] += j in act
    return {j: hits[j] / n_sub for j in features}


def build_rules(d: Data, final: dict, z_real: np.ndarray, placebo_z: np.ndarray | None,
                vault_fit: dict | None = None) -> pd.DataFrame:
    """final: output of pipeline.select_and_fit on all pre-vault data."""
    X = d.X
    pre = ~d.vault
    frame, mod = final["frame"], final["model"]
    q_all = models.bh_qvalues(2 * _norm_sf(np.abs(z_real)))
    if mod is None:
        return pd.DataFrame()
    active = [(int(c), float(w), float(v)) for c, w, v in zip(final["cols"], mod.w, mod.v) if w or v]
    if not active:
        return pd.DataFrame()
    stab = stability(d, X, pre, frame, final["frac"], [a[0] for a in active])
    y, lp = final["y"], final["logP0"]
    seasons = sorted(set(d.season[pre]))
    early = pre & np.isin(d.season, seasons[: len(seasons) // 2 + 1])
    late = pre & ~early
    leagues = d.m.division[pre].value_counts().index[:10]
    rows = []
    for j, w, v in active:
        name = d.cols[j]
        x = X[:, j].astype(float)
        u = models.univariate(x[pre], y[pre], lp[pre])
        ue = models.univariate(x[early], y[early], lp[early])
        ul = models.univariate(x[late], y[late], lp[late])
        signs = []
        for lg in leagues:
            msk = pre & (d.m.division == lg).to_numpy()
            if (x[msk] != 0).sum() >= 50:
                signs.append(np.sign(models.univariate(x[msk], y[msk], lp[msk])["beta"]))
        consistent = int(sum(s == np.sign(u["beta"]) for s in signs))
        pz = placebo_z[:, j] if placebo_z is not None else None
        pct = float((np.abs(pz) < abs(z_real[j])).mean() * 100) if pz is not None else None
        z_cal = float(z_real[j] / max(1.0, np.std(pz))) if pz is not None else None
        uv = models.univariate(x[d.vault], final["y_all"][d.vault], vault_fit["logP0"][d.vault]) \
            if vault_fit is not None and (x[d.vault] != 0).sum() >= 30 else None
        checks = {
            "stability ≥ 0.7": stab[j] >= 0.7,
            "BH q ≤ 0.05": q_all[j] <= 0.05,
            "replicates out of time": np.sign(ue["beta"]) == np.sign(ul["beta"]) and ul["p"] <= 0.10,
            "≥3 leagues agree": consistent >= 3,
            "placebo percentile ≥ 95": pct is not None and pct >= 95,
        }
        status = "provisional" if all(checks.values()) else "candidate"
        rows.append({
            "rule_key": name, "statement": statement(name, frame, u["effect_pp"]), "frame": frame,
            "family": lattice.META.get(name, {}).get("family"), "structure": lattice.META.get(name, {}).get("structure"),
            "coef_team1": 2 * w, "coef_draw": v, "effect_pp": u["effect_pp"], "beta": u["beta"], "se": u["se"],
            "ci_low_pp": u["effect_pp"] * (u["beta"] - 1.96 * u["se"]) / u["beta"] if u["beta"] else 0.0,
            "ci_high_pp": u["effect_pp"] * (u["beta"] + 1.96 * u["se"]) / u["beta"] if u["beta"] else 0.0,
            "n_active": u["n_active"], "q_value": float(q_all[j]), "stability": stab[j],
            "early_beta": ue["beta"], "late_beta": ul["beta"], "late_p": ul["p"],
            "leagues_consistent": consistent, "leagues_tested": len(signs),
            "placebo_percentile": pct, "z": float(z_real[j]), "z_placebo_calibrated": z_cal,
            "vault_beta": uv["beta"] if uv else None, "vault_p": uv["p"] if uv else None,
            "checks": checks, "status": status,
            "orb_curve": orb_curve(name, x[pre], y[pre], lp[pre]),
        })
    return pd.DataFrame(rows).sort_values(["status", "q_value"], ascending=[False, True])


def top_univariate(d: Data, z_real, placebo_z, k=25) -> pd.DataFrame:
    """Strongest single primitives overall (exploratory; shown with placebo context)."""
    q = models.bh_qvalues(2 * _norm_sf(np.abs(z_real)))
    order = np.argsort(-np.abs(z_real))[:k]
    rows = []
    for j in order:
        pz = placebo_z[:, j] if placebo_z is not None else None
        rows.append({"feature": d.cols[j], "desc": lattice.META.get(d.cols[j], {}).get("desc", d.cols[j]),
                     "family": lattice.META.get(d.cols[j], {}).get("family"),
                     "z": float(z_real[j]), "q_value": float(q[j]),
                     "placebo_sd": float(np.std(pz)) if pz is not None else None,
                     "placebo_percentile": float((np.abs(pz) < abs(z_real[j])).mean() * 100) if pz is not None else None})
    return pd.DataFrame(rows)


def _norm_sf(x):
    from scipy.stats import norm
    return norm.sf(x)
