"""Render FINDINGS.md from data/models/*.json and data/work/tribunal.parquet."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from astrofoot.config import MODELS, WORK  # noqa: E402


def j(name):
    p = MODELS / name
    return json.loads(p.read_text()) if p.exists() else None


def f(x, d=5):
    return "—" if x is None else f"{x:+.{d}f}"


def ci(dr, d=5):
    return f"{f(dr['delta'], d)} [{f(dr['ci95'][0], d)}, {f(dr['ci95'][1], d)}]"


def main():
    ev, cx = j("evaluation.json"), j("codex.json")
    L = ["# Findings", ""]
    if ev is None:
        L.append("No evaluation yet.")
    else:
        e = ev["engine4"]
        L += [f"_Generated {cx['generated_at'] if cx else ev['generated_at']} · lattice {ev['lattice_version']} · "
              f"{ev['n_matches']:,} matches · {ev['n_features']:,} astrological primitives_", ""]
        if cx and cx.get("null_statement"):
            L += ["## Headline", "", cx["null_statement"], ""]
        L += ["## Walk-forward (seasons 2020/21–2024/25, out of sample)", "",
              "ΔRPS is model minus market-based control model (M0); negative is better. 95% CI from a matchday block bootstrap.", "",
              "| Model | RPS | Log loss | Accuracy | ΔRPS vs M0 [95% CI] |", "|---|---|---|---|---|",
              f"| Market odds (de-vigged) | {e['market']['rps']:.5f} | {e['market']['logloss']:.5f} | {100 * e['market']['accuracy']:.2f}% | |",
              f"| M0 market + controls | {e['m0']['rps']:.5f} | {e['m0']['logloss']:.5f} | {100 * e['m0']['accuracy']:.2f}% | 0 |"]
        for lab, s in (("M1 classical engines re-weighted", ev["classical_m1"]), ("Engine 4 (Emergent Codex)", e),
                       ("Engine 4, coin-flip frame (negative control)", ev["coin_control"])):
            L.append(f"| {lab} | {s['engine4']['rps']:.5f} | {s['engine4']['logloss']:.5f} | "
                     f"{100 * s['engine4']['accuracy']:.2f}% | {ci(s['delta_rps_vs_m0'], 6)} |")
        L += ["", "Note: M0 (market + calendar/scheduling controls) is itself slightly *worse* than the raw de-vigged odds "
              f"(RPS {e['m0']['rps']:.5f} vs {e['market']['rps']:.5f}): the ~90 control covariates add a little noise. "
              "Engine 4 is benchmarked against M0 so that astrology is never credited with calendar effects. "
              "Since it does not beat M0, it falls further short of the raw market. The app therefore shows "
              "raw market probabilities whenever the Engine 4 gate is closed.",
              "", "Per fold, inner validation chose: " + "; ".join(
            f"{x['season']}: {x['frame']}, {x['n_active']} primitives" for x in e["folds"]), ""]
        L += ["## Raw accuracy of the classical engines (pre-vault, favourite frame)", "",
              "| System | Accuracy | Picks favourite | Picks draw | n |", "|---|---|---|---|---|"]
        for k, r in ev["engine_accuracy"].items():
            L.append(f"| {k} | {100 * r['accuracy']:.1f}% | {100 * r['picks_favourite']:.1f}% | "
                     f"{100 * r['picks_draw']:.1f}% | {r['n']:,} |")
        L += ["", "## Structural declarations", "",
              "| Structure | Primitives | ΔRPS vs M0 [95% CI] |", "|---|---|---|"]
        for k, s in ev["structures"].items():
            L.append(f"| {k} | {s['n_features']} | {ci(s['delta_rps_vs_m0'], 6)} |")
        L.append("")
    power = ROOT / "data" / "power.log"
    selftest = ROOT / "data" / "selftest.log"
    if power.exists() or selftest.exists():
        L += ["## Can the pipeline find a real effect? (planted-signal tests)", "",
              "Outcomes were simulated from the market model plus a planted effect for *Mars in sidereal Aries*, "
              "a configuration present in ~9% of test matches. The planted effect is a team1-vs-team2 log-odds "
              "shift (0.2 ≈ +3.4 pp, 0.4 ≈ +6.7 pp, 0.8 ≈ +13.1 pp win probability).", "", "```"]
        for p in (selftest, power):
            if p.exists():
                L += [ln for ln in p.read_text().splitlines() if ln.startswith("[")]
        L += ["```", "",
              "Reading: effects of about +6.7 pp on a configuration this common are found and validated out of sample. "
              "+3.4 pp is recovered by the final fit but is too thin to validate, because the configuration is "
              "clustered in calendar time. The null run (no planted effect) keeps nothing. A null result on the real "
              "sky therefore rules out effects of roughly this size or larger for common configurations. It cannot rule out "
              "smaller effects, or effects of rare configurations.", ""]
    tp = WORK / "tribunal.parquet"
    if tp.exists():
        t = pd.read_parquet(tp)
        L += ["## Doctrine Tribunal", "", "Verdicts: " + ", ".join(f"{k}: {v}" for k, v in t.verdict.value_counts().items()), "",
              "Ten strongest doctrines by raw p-value (still subject to Holm correction across all of them):", "",
              "| Doctrine | Matches | Hit rate | Market expected | Effect (pp) | p | p (Holm) | Verdict |",
              "|---|---|---|---|---|---|---|---|"]
        for r in t.sort_values("p").head(10).itertuples():
            L.append(f"| {r.doctrine} | {r.n_active:,} | {100 * r.hit_rate:.1f}% | {100 * r.market_expected:.1f}% | "
                     f"{r.effect_pp:+.2f} | {r.p:.3f} | {r.p_holm:.3f} | {r.verdict} |")
        L.append("")
    if cx:
        L += ["## Codex", "", f"Version {cx['version']}. Gate: {'OPEN' if cx['gate']['engine4_in_synthesis'] else 'closed'}"
              + (f" ({'; '.join(cx['gate']['reasons'])})" if cx['gate']['reasons'] else "") + ".", ""]
        if cx.get("placebo"):
            p = cx["placebo"]
            L.append(f"Placebo skies: {p['n']} runs. The real sky beat {p['percentile']:.0f}% of them.")
        if cx.get("vault"):
            v = cx["vault"]
            L.append(f"Vault (one-shot, {v['n']:,} matches from 2025/26 onward, accessed {v['accessed_at']}): ΔRPS {ci(v['delta_rps_vs_m0'], 6)}.")
        L += ["", "| Status | Rule | Effect (pp) | q | Stability | Leagues | Placebo pct |", "|---|---|---|---|---|---|---|"]
        for r in cx["rules"]:
            pct = "—" if r["placebo_percentile"] is None else f"{r['placebo_percentile']:.0f}"
            L.append(f"| {r['status']} | {r['statement']} | {r['effect_pp']:+.2f} | {r['q_value']:.3f} | "
                     f"{r['stability']:.1f} | {r['leagues_consistent']}/{r['leagues_tested']} | {pct} |")
        if not cx["rules"]:
            L.append("| — | The final model kept no primitive. | | | | | |")
        L += ["", "### Strongest single primitives (exploratory)", "",
              "| Primitive | z | BH q | Placebo sd of z | Placebo pct |", "|---|---|---|---|---|"]
        for r in cx["top_univariate"][:12]:
            ps = "—" if r["placebo_sd"] is None else f"{r['placebo_sd']:.2f}"
            pp = "—" if r["placebo_percentile"] is None else f"{r['placebo_percentile']:.0f}"
            L.append(f"| {r['desc']} | {r['z']:+.2f} | {r['q_value']:.3f} | {ps} | {pp} |")
    (ROOT / "FINDINGS.md").write_text("\n".join(L) + "\n")
    print("FINDINGS.md written")


if __name__ == "__main__":
    main()
