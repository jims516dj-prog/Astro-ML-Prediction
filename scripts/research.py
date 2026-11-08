"""Research pipeline CLI.

  python scripts/research.py prepare            # dataset + real sky + classical engines
  python scripts/research.py evaluate           # walk-forward: Engine 4, COIN control, M1, structures, Tribunal
  python scripts/research.py placebo --k 10     # placebo skies (time/date/place shift), identical pipeline
  python scripts/research.py codex              # final fit, Codex rules, vault (once), gate, artifact
  python scripts/research.py overunder          # over/under 2.5 and team to score: calibration + backtests
  python scripts/research.py all --k 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrofoot import classical_batch, codex, dataset, lattice, models, overunder, pipeline, teamgoals  # noqa: E402
from astrofoot import doublechance, form  # noqa: E402
from astrofoot import sky as skymod  # noqa: E402
from astrofoot.config import LATTICE_VERSION, LIVING, MODELS, WORK  # noqa: E402

# Placebo results are only comparable within one lattice version (same features, same pipeline).
PLACEBO_DIR = MODELS / "placebo" / LATTICE_VERSION
PLACEBO_DIR.mkdir(exist_ok=True, parents=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_json(name, default=None):
    p = MODELS / name
    return json.loads(p.read_text()) if p.exists() else default


def prepare():
    m = dataset.build()
    log("matches", len(m), "of which settled live forecasts:", int((m.data_source == "live ledger (football-data.co.uk)").sum()))
    s = skymod.compute_sky(m, "real")
    log("real sky ready")
    classical_batch.run(m, s)
    log("classical engines ready")


def _summ(oof, name):
    oof.to_pickle(WORK / f"oof_{name}.pkl")
    return pipeline.summarise(oof)


def evaluate():
    d = pipeline.load()
    E = pd.read_parquet(WORK / "engines_real.parquet")
    rep = {"generated_at": pipeline.now(), "lattice_version": LATTICE_VERSION,
           "n_matches": int(len(d.m)), "n_features": len(d.cols)}
    log("Engine 4 walk-forward")
    rep["engine4"] = _summ(pipeline.walk_forward(d), "engine4")
    log("ΔRPS", rep["engine4"]["delta_rps_vs_m0"])
    log("COIN-frame negative control")
    rep["coin_control"] = _summ(pipeline.walk_forward(d, frames=["COIN"]), "coin")
    log("M1 classical re-weighting")
    rep["classical_m1"] = _summ(pipeline.classical_walk_forward(d, E), "m1")
    rep["engine_accuracy"] = pipeline.engine_accuracy(d, E)
    log("Doctrine Tribunal")
    trib = pipeline.tribunal(d, E)
    trib.to_parquet(WORK / "tribunal.parquet")
    rep["tribunal_summary"] = trib.groupby(["book", "verdict"]).size().unstack(fill_value=0).to_dict("index")
    if LIVING:      # zodiac / house-system comparisons were settled under L-2026.1; not repeated weekly
        rep["structures"] = (load_json("evaluation.json") or {}).get("structures", {})
        pipeline.save_json(rep, "evaluation.json")
        log("evaluation saved")
        return
    log("structural comparisons")
    meta = lattice.meta_frame().reindex(d.cols)
    struct = {}
    base = meta.block.isin(["S", "A"]).to_numpy()
    for z in lattice.ZODIACS:
        sel = base | ((meta.block == "Z") & (meta.structure == z)).to_numpy() | \
            ((meta.block == "H") & meta.structure.fillna("").str.endswith(z)).to_numpy() | \
            ((meta.block == "H") & meta.structure.isin(["placidus", "equal", "regiomontanus", "campanus"])).to_numpy()
        struct[f"zodiac:{z}"] = _struct_run(d, sel, f"zod_{z}")
    for hsys in lattice.HOUSES:
        sel = base | (meta.block == "Z").to_numpy() | \
            ((meta.block == "H") & meta.structure.fillna("").str.startswith(hsys)).to_numpy()
        struct[f"houses:{hsys}"] = _struct_run(d, sel, f"hs_{hsys}")
    rep["structures"] = struct
    pipeline.save_json(rep, "evaluation.json")
    log("evaluation saved")


def _struct_run(d, sel, name):
    oof = pipeline.walk_forward(d, X=d.X[:, sel])
    s = pipeline.summarise(oof)
    log(name, s["delta_rps_vs_m0"])
    return {"n_features": int(sel.sum()), "delta_rps_vs_m0": s["delta_rps_vs_m0"],
            "frames": [f["frame"] for f in s["folds"]]}


def placebo(k: int, kinds=("time_shift", "date_shift", "place_shift"), fresh: bool = False):
    if fresh:   # the data has grown since the last placebo run: recompute them all against it
        for p in PLACEBO_DIR.glob("*.npz"):
            p.unlink()
    m = pd.read_parquet(WORK / "matches.parquet")
    for seed in range(1, k + 1):
        for kind in kinds:
            out = PLACEBO_DIR / f"{kind}_{seed}.npz"
            if out.exists():
                continue
            t = time.time()
            s = skymod.compute_sky(m, kind, seed)
            X = lattice.build(s)
            # the books' engines are re-run on the placebo charts too, so their testimonies are
            # scrambled exactly like the sky primitives
            E = classical_batch.run(m, s, out_path=False)
            d = pipeline.load(X, E=E)
            oof = pipeline.walk_forward(d)
            summ = pipeline.summarise(oof)
            pre = ~d.vault
            _, lp, y = pipeline._m0(d, "FAV", pre)
            z = pipeline.score_z(d.X[pre], y[pre], lp[pre])
            np.savez(out, delta=summ["delta_rps_vs_m0"]["delta"], z=z, cols=np.array(d.cols))
            skymod.sky_path(kind, seed).unlink(missing_ok=True)   # keep disk small; seeds are reproducible
            log(f"placebo {kind} #{seed}: ΔRPS {summ['delta_rps_vs_m0']['delta']:+.6f} ({time.time() - t:.0f}s)")
            del d, X, s


def load_placebos(cols):
    deltas, zs, kinds = [], [], []
    for p in sorted(PLACEBO_DIR.glob("*.npz")):
        z = np.load(p, allow_pickle=True)
        zmap = dict(zip(z["cols"], z["z"]))
        deltas.append(float(z["delta"]))
        zs.append([zmap.get(c, 0.0) for c in cols])
        kinds.append(p.stem.rsplit("_", 1)[0])
    if not deltas:
        return None, None, []
    return np.array(deltas), np.array(zs), kinds


def make_codex():
    ev = load_json("evaluation.json")
    if ev is None:
        raise SystemExit("run `evaluate` first")
    d = pipeline.load()
    pre = ~d.vault
    log("final fit on all " + ("data (living engine)" if LIVING else "pre-vault seasons"))
    final = pipeline.select_and_fit(d, d.X, pre)
    final["y_all"] = final["y"]
    m0s = {fr: pipeline._m0(d, fr, pre)[0] for fr in pipeline.FRAMES}
    _, lp_fav, y_fav = pipeline._m0(d, "FAV", pre)
    z_real = pipeline.score_z(d.X[pre], y_fav[pre], lp_fav[pre])
    deltas, pz, kinds = load_placebos(d.cols)
    real_delta = ev["engine4"]["delta_rps_vs_m0"]["delta"]
    placebo = None
    if deltas is not None:
        placebo = {"n": int(len(deltas)), "deltas": deltas.tolist(), "kinds": kinds,
                   "real_delta": real_delta,
                   "percentile": float((deltas > real_delta).mean() * 100)}

    # Vault: evaluated once (for L-2026.1), then frozen in vault.json. The living engine trains on the
    # vault seasons too, so it is not re-run; the prospective ledger is the out-of-sample check now.
    vault = load_json("vault.json", {})
    if LIVING:
        log("living engine: vault spent (", vault.get("lattice_version"), vault.get("accessed_at"), ") — not re-run")
    elif vault.get("lattice_version") != LATTICE_VERSION:
        log("VAULT evaluation (one-shot for this lattice version)")
        y = final["y"][d.vault]
        lp = final["logP0"][d.vault]
        P0 = np.exp(lp); P0 /= P0.sum(1, keepdims=True)
        P2 = P0 if final["model"] is None else final["model"].predict(d.X[np.ix_(d.vault, final["cols"])], lp)
        dd = models.block_bootstrap_delta(models.rps(P2, y), models.rps(P0, y), d.day[d.vault])
        vault = {"lattice_version": LATTICE_VERSION, "accessed_at": pipeline.now(), "n": int(d.vault.sum()),
                 "frame": final["frame"], "engine4": models.scores(P2, y), "m0": models.scores(P0, y),
                 "delta_rps_vs_m0": dd}
        pipeline.save_json(vault, "vault.json")
    else:
        log("vault already evaluated for", LATTICE_VERSION, "at", vault["accessed_at"], "— not re-run")

    log("Codex rules")
    rules = codex.build_rules(d, final, z_real, pz, vault_fit={"logP0": final["logP0"]})
    top = codex.top_univariate(d, z_real, pz)
    wf = ev["engine4"]["delta_rps_vs_m0"]
    gate_reasons = []
    if not wf["ci95"][1] < 0:
        gate_reasons.append("walk-forward ΔRPS vs market model: 95% CI does not exclude zero")
    if placebo is None:
        gate_reasons.append("placebo skies not yet run")
    elif placebo["percentile"] < 95:
        gate_reasons.append(f"real sky beats only {placebo['percentile']:.0f}% of placebo skies (needs ≥95%)")
    gate = {"engine4_in_synthesis": not gate_reasons, "reasons": gate_reasons}
    n_prov = int((rules.status == "provisional").sum()) if len(rules) else 0
    null_statement = None
    if not gate["engine4_in_synthesis"] and n_prov == 0:
        null_statement = (
            f"Across {ev['engine4']['engine4']['n']:,} out-of-sample matches (seasons 2020/21–2024/25), no "
            f"combination of {len(d.cols):,} astrological primitives improved on the market-based control "
            f"model (ΔRPS {wf['delta']:+.6f}, 95% CI {wf['ci95'][0]:+.6f} to {wf['ci95'][1]:+.6f})"
            + (f"; the real sky ranked better than {placebo['percentile']:.0f}% of {placebo['n']} placebo skies" if placebo else "")
            + ". No rule reached Provisional status.")
    versions = sorted(MODELS.glob("engine4_v*.joblib"))
    version = f"v{len(versions) + 1}"
    art = {"version": version, "trained_at": pipeline.now(), "lattice_version": LATTICE_VERSION,
           "frame": final["frame"], "frac": final["frac"], "model": final["model"],
           "cols": [d.cols[j] for j in final["cols"]], "m0": m0s, "gate": gate,
           "classical": any(c.startswith("C.") for c in d.cols), "n_matches": int(len(d.m)),
           "n_live": int((d.m.data_source == "live ledger (football-data.co.uk)").sum())}
    joblib.dump(art, MODELS / f"engine4_{version}.joblib")
    joblib.dump(art, MODELS / "engine4_current.joblib")
    report = {
        "version": version, "generated_at": pipeline.now(), "lattice_version": LATTICE_VERSION,
        "final": {"frame": final["frame"], "frac": final["frac"], "val_gain": final["val_gain"],
                  "n_active": int(final["model"].active.sum()) if final["model"] is not None else 0},
        "gate": gate, "placebo": placebo, "vault": vault, "null_statement": null_statement,
        "rules": rules.to_dict("records") if len(rules) else [],
        "top_univariate": top.to_dict("records"),
    }
    pipeline.save_json(report, "codex.json")
    hist = load_json("history.json", [])
    hist.append({"version": version, "trained_at": report["generated_at"], "delta_rps": wf["delta"],
                 "ci95": wf["ci95"], "placebo_percentile": placebo["percentile"] if placebo else None,
                 "gate_open": gate["engine4_in_synthesis"], "n_rules": len(report["rules"]),
                 "n_provisional": n_prov, "lattice_version": LATTICE_VERSION, "n_matches": art["n_matches"],
                 "n_live": art["n_live"], "n_active": report["final"]["n_active"]})
    pipeline.save_json(hist, "history.json")
    log("codex saved", version, "gate", gate)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prepare", "evaluate", "placebo", "codex", "all", "living", "overunder"])
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--fresh", action="store_true", help="placebo: discard this version's previous placebo skies")
    a = ap.parse_args()
    # living = the weekly retrain: rebuild data (history + settled live matches), evaluate, refit, publish
    if a.stage in ("prepare", "all", "living"):
        prepare()
    if a.stage in ("evaluate", "all", "living"):
        evaluate()
    if a.stage in ("placebo", "all"):
        placebo(a.k, fresh=a.fresh)
    if a.stage in ("codex", "all", "living"):
        make_codex()
    if a.stage in ("overunder", "all", "living"):
        res = overunder.backtest(pd.read_parquet(WORK / "matches.parquet"), pd.read_parquet(WORK / "engines_real.parquet"))
        overunder.write(res)
        log(f"over/under: calibration b={res['calibration']['b']:.3f}; top picks hit {res['top']['hit_rate']:.3f} "
            f"vs {res['top']['expected']:.3f} expected; Rao lift {res['engines']['rao']['lift']:+.4f}, "
            f"Chokoisky lift {res['engines']['chokoisky']['lift']:+.4f}")
        tg = teamgoals.backtest(pd.read_parquet(WORK / "matches.parquet"), pd.read_parquet(WORK / "engines_real.parquet"))
        teamgoals.write(tg)
        log(f"team to score: top picks hit {tg['top']['hit_rate']:.3f} vs {tg['top']['expected']:.3f} expected; "
            f"Rao lift {tg['engines']['rao']['lift']:+.4f}, Chokoisky lift {tg['engines']['chokoisky']['lift']:+.4f}")
        guide = teamgoals.scoring_guide(pd.read_parquet(WORK / "matches.parquet"))
        teamgoals.write_guide(guide)
        log(f"scoring guide: home scored {guide['home_rate']:.3f}, away {guide['away_rate']:.3f} of {guide['n_matches']:,}")
        dc = doublechance.backtest(pd.read_parquet(WORK / "matches.parquet"), pd.read_parquet(WORK / "engines_real.parquet"))
        doublechance.write(dc)
        log(f"double chance: picks hit {dc['all']['hit_rate']:.3f} vs {dc['all']['expected']:.3f} expected; "
            f"over 1.5 picks hit {tg['over15']['all']['hit_rate']:.3f} vs {tg['over15']['all']['expected']:.3f}")
        fm = form.backtest(pd.read_parquet(WORK / "matches.parquet"), pd.read_parquet(WORK / "engines_real.parquet"))
        form.write(fm)
        log(f"form check: log loss market {fm['all']['log_loss']['mkt']:.4f}, market+form "
            f"{fm['all']['log_loss']['mkt+form']:.4f} (form weight {fm['all']['coef_form']:+.3f})")
