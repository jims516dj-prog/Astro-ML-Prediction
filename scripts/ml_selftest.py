"""ML correctness tests on the real lattice (spec §11.4-D).

  signal  : outcomes simulated from the market model + an injected astrological effect.
            The pipeline must keep the injected primitive and beat the market model.
  null    : outcomes simulated from the market model only. The pipeline must NOT beat it.
  power   : injected effects of several sizes -> the minimum effect this pipeline can detect.

Both use the real 107k-match lattice, so they also test the screening and selection code
under the real feature correlations.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from astrofoot import models, pipeline  # noqa: E402

# A common configuration (~8% of matches). A rare one such as "Mars just past the Ascendant"
# (1.2% of matches, mean kernel 0.2) cannot be detected even with a planted effect of 0.6:
# its z is ~2, rank ~80 of 2,463. Detectability depends on frequency x effect size AND on
# calendar clustering: Mars-in-Aries exposures sit mostly in 2020/21, so a +3.4 pp effect is
# recovered by the final fit but too thin to validate in walk-forward (oracle ΔRPS -9e-5).
INJECT = "Z.lahiri.Ma.sign.0"  # Mars in sidereal Aries
EFFECT = 0.40                  # team1-vs-team2 log-odds shift when active (~ +6.7 pp win prob)
POWER_EFFECTS = (0.2, 0.4, 0.8)


def simulate(d, inject: bool, seed: int, effect: float = EFFECT):
    rng = np.random.default_rng(seed)
    _, lp, _ = pipeline._m0(d, "FAV", ~d.vault)
    if inject:
        j = d.cols.index(INJECT)
        x = d.X[:, j].astype(float)
        shift = np.column_stack([effect * x / 2, 0 * x, -effect * x / 2])
        lp = lp + shift
    P = np.exp(lp)
    P /= P.sum(1, keepdims=True)
    u = rng.random(len(P))[:, None]
    return (u > np.cumsum(P, 1)).sum(1)


def run(kind: str, seed: int = 0, effect: float = EFFECT, check: bool = True):
    d = pipeline.load()
    y = simulate(d, kind != "null", seed, effect)
    for f in d.frames.values():
        f["y"] = y                      # same simulated label in every frame (frame = FAV here)
    oof = pipeline.walk_forward(d, frames=["FAV"])
    s = pipeline.summarise(oof)
    fit = pipeline.select_and_fit(d, d.X, ~d.vault, frames=["FAV"])
    kept = [d.cols[c] for c, w, v in zip(fit["cols"], fit["model"].w, fit["model"].v) if w or v] \
        if fit["model"] is not None else []
    dr = s["delta_rps_vs_m0"]
    print(f"[{kind} effect={effect if kind != 'null' else 0}] ΔRPS {dr['delta']:+.6f} CI {dr['ci95'][0]:+.6f}..{dr['ci95'][1]:+.6f}; "
          f"recovered={INJECT in kept}; kept {len(kept)}: {kept[:8]}", flush=True)
    if not check:
        return INJECT in kept, dr
    if kind == "signal":
        assert INJECT in kept, "injected primitive not recovered"
        assert dr["ci95"][1] < 0, "injected signal did not beat the market model out of sample"
    else:
        assert not dr["ci95"][1] < 0, "null data produced a significant 'edge' (false positive)"
    print(f"[{kind}] PASS")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["signal", "null", "both", "power"])
    a = ap.parse_args()
    if a.kind == "power":
        for e in POWER_EFFECTS:
            run("power", effect=e, check=False)
    else:
        for k in (["signal", "null"] if a.kind == "both" else [a.kind]):
            run(k)
