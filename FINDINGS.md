# Findings

_Generated 2026-10-27T20:54:03 · lattice L-2026.1 · 107,263 matches · 2,463 astrological primitives_

## Headline

Across 58,568 out-of-sample matches (seasons 2020/21–2024/25), no combination of 2,463 astrological primitives improved on the market-based control model (ΔRPS +0.000001, 95% CI -0.000001 to +0.000004); the real sky ranked better than 76% of 21 placebo skies. No rule reached Provisional status.

## Walk-forward (seasons 2020/21–2024/25, out of sample)

ΔRPS is model minus market-based control model (M0); negative is better. 95% CI from a matchday block bootstrap.

| Model | RPS | Log loss | Accuracy | ΔRPS vs M0 [95% CI] |
|---|---|---|---|---|
| Market odds (de-vigged) | 0.20421 | 1.00285 | 50.20% | |
| M0 market + controls | 0.20467 | 1.00494 | 50.06% | 0 |
| M1 classical engines re-weighted | 0.20460 | 1.00473 | 50.04% | +0.000021 [-0.000002, +0.000046] |
| Engine 4 (Emergent Codex) | 0.20467 | 1.00495 | 50.05% | +0.000001 [-0.000001, +0.000004] |
| Engine 4, coin-flip frame (negative control) | 0.20471 | 1.00506 | 50.05% | +0.000000 [+0.000000, +0.000000] |

Note: M0 (market + calendar/scheduling controls) is itself slightly *worse* than the raw de-vigged odds (RPS 0.20467 vs 0.20421): the ~90 control covariates add a little noise. Engine 4 is benchmarked against M0 so that astrology is never credited with calendar effects. Since it does not beat M0, it falls further short of the raw market. The app therefore shows raw market probabilities whenever the Engine 4 gate is closed.

Per fold, inner validation chose: 2020/21: HOME, 1 primitives; 2021/22: FAV, 0 primitives; 2022/23: FAV, 0 primitives; 2023/24: FAV, 0 primitives; 2024/25: FAV, 0 primitives

## Raw accuracy of the classical engines (pre-vault, favourite frame)

| System | Accuracy | Picks favourite | Picks draw | n |
|---|---|---|---|---|
| Rao | 33.0% | 33.7% | 20.6% | 98,975 |
| Chokoisky | 32.9% | 33.6% | 17.0% | 98,975 |
| Frawley | 38.4% | 55.0% | 5.3% | 97,326 |
| Always favourite | 50.3% | 100.0% | 0.0% | 98,975 |
| Market (most likely outcome) | 50.3% | 99.9% | 0.1% | 98,975 |

## Structural declarations

| Structure | Primitives | ΔRPS vs M0 [95% CI] |
|---|---|---|
| zodiac:tropical | 1753 | +0.000010 [-0.000003, +0.000022] |
| zodiac:lahiri | 1778 | +0.000021 [-0.000018, +0.000060] |
| houses:placidus | 1076 | +0.000014 [-0.000006, +0.000033] |
| houses:equal | 1078 | +0.000028 [+0.000000, +0.000054] |
| houses:regiomontanus | 1078 | +0.000001 [-0.000001, +0.000004] |
| houses:campanus | 1078 | +0.000016 [-0.000014, +0.000048] |
| houses:whole_sign | 1221 | +0.000006 [-0.000008, +0.000018] |

## Can the pipeline find a real effect? (planted-signal tests)

Outcomes were simulated from the market model plus a planted effect for *Mars in sidereal Aries*, a configuration present in ~9% of test matches. The planted effect is a team1-vs-team2 log-odds shift (0.2 ≈ +3.4 pp, 0.4 ≈ +6.7 pp, 0.8 ≈ +13.1 pp win probability).

```
[signal effect=0.4] ΔRPS -0.000059 CI -0.000085..-0.000036; recovered=True; kept 1: ['Z.lahiri.Ma.sign.0']
[signal] PASS
[null effect=0] ΔRPS +0.000006 CI -0.000015..+0.000028; recovered=False; kept 0: []
[null] PASS
[power effect=0.2] ΔRPS +0.000007 CI -0.000011..+0.000027; recovered=True; kept 1: ['Z.lahiri.Ma.sign.0']
[power effect=0.4] ΔRPS -0.000059 CI -0.000085..-0.000036; recovered=True; kept 1: ['Z.lahiri.Ma.sign.0']
[power effect=0.8] ΔRPS -0.000345 CI -0.000461..-0.000246; recovered=True; kept 1: ['Z.lahiri.Ma.sign.0']
```

Reading: effects of about +6.7 pp on a configuration this common are found and validated out of sample. +3.4 pp is recovered by the final fit but is too thin to validate, because the configuration is clustered in calendar time. The null run (no planted effect) keeps nothing. A null result on the real sky therefore rules out effects of roughly this size or larger for common configurations. It cannot rule out smaller effects, or effects of rare configurations.

## Doctrine Tribunal

Verdicts: not supported: 74

Ten strongest doctrines by raw p-value (still subject to Holm correction across all of them):

| Doctrine | Matches | Hit rate | Market expected | Effect (pp) | p | p (Holm) | Verdict |
|---|---|---|---|---|---|---|---|
| chokoisky.d1_cusp.Sa | 9,270 | 39.9% | 39.1% | +1.07 | 0.017 | 1.000 | not supported |
| rao.score | 38,493 | 36.9% | 36.4% | +0.46 | 0.039 | 1.000 | not supported |
| chokoisky.d1_cusp.Ju | 8,839 | 37.1% | 37.8% | -0.77 | 0.096 | 1.000 | not supported |
| chokoisky.tara.Wasat | 3,925 | 37.3% | 36.1% | +1.13 | 0.102 | 1.000 | not supported |
| chokoisky.victory_house | 80,548 | 33.5% | 33.2% | +0.24 | 0.111 | 1.000 | not supported |
| chokoisky.d9_cusp.Ma | 2,676 | 38.6% | 37.0% | +1.32 | 0.115 | 1.000 | not supported |
| rao.fans | 30,732 | 36.5% | 36.1% | +0.39 | 0.119 | 1.000 | not supported |
| frawley.fortuna_antiscion_cusp1 | 1,500 | 52.9% | 50.6% | +1.74 | 0.124 | 1.000 | not supported |
| frawley.body.inside_enemy_house | 4,790 | 34.3% | 33.3% | +0.96 | 0.124 | 1.000 | not supported |
| frawley.l1_opp_fortuna | 3,451 | 22.2% | 23.1% | -1.14 | 0.127 | 1.000 | not supported |

## Codex

Version v1. Gate: closed (walk-forward ΔRPS vs market model: 95% CI does not exclude zero; real sky beats only 76% of placebo skies (needs ≥95%)).

Placebo skies: 21 runs. The real sky beat 76% of them.
Vault (one-shot, 8,288 matches from 2025/26 onward, accessed 2026-10-27T20:54:03): ΔRPS +0.000000 [+0.000000, +0.000000].

| Status | Rule | Effect (pp) | q | Stability | Leagues | Placebo pct |
|---|---|---|---|---|---|---|
| — | The final model kept no primitive. | | | | | |

### Strongest single primitives (exploratory)

| Primitive | z | BH q | Placebo sd of z | Placebo pct |
|---|---|---|---|---|
| lord of the 10th (team1) in the 6th house (Campanus, lahiri) | +3.75 | 0.442 | 1.05 | 100 |
| lord of the 10th (team1) in the 6th house (Placidus, lahiri) | +3.31 | 0.641 | 0.91 | 100 |
| lord of the 7th (team2) in the 12th house (Campanus, lahiri) | -3.23 | 0.641 | 1.36 | 100 |
| lord of the 10th (team1) in the 7th house (Placidus, lahiri) | -3.14 | 0.641 | 0.94 | 100 |
| lord of the 10th (team1) in the 6th house (Regiomontanus, lahiri) | +3.12 | 0.641 | 1.00 | 100 |
| Sun in the 12th house (Placidus) | -3.12 | 0.641 | 1.21 | 100 |
| lord of the 10th (team1) in the 11th house (Campanus, lahiri) | +3.02 | 0.641 | 1.01 | 100 |
| lord of the 10th (team1) in the 7th house (Regiomontanus, lahiri) | -3.02 | 0.641 | 0.90 | 100 |
| lord of the 10th (team1) in the 7th house (Equal, lahiri) | -3.00 | 0.641 | 0.74 | 100 |
| Moon in Gemini | -2.88 | 0.641 | 1.34 | 67 |
| malefics in team1's victory houses minus team2's (Campanus, lahiri) | +2.87 | 0.641 | 1.08 | 100 |
| malefics in team1's victory houses minus team2's (Campanus, tropical) | +2.87 | 0.641 | 1.08 | 100 |
