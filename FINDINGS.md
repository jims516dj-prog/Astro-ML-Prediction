# Findings

_Generated 2026-11-02T17:01:03 · lattice L-2026.2 · 107,462 matches · 2,552 astrological primitives_

## Headline

Across 67,055 out-of-sample matches (seasons 2020/21–2024/25), no combination of 2,552 astrological primitives improved on the market-based control model (ΔRPS +0.000055, 95% CI -0.000012 to +0.000124). No rule reached Provisional status.

## Walk-forward (seasons 2020/21–2024/25, out of sample)

ΔRPS is model minus market-based control model (M0); negative is better. 95% CI from a matchday block bootstrap.

| Model | RPS | Log loss | Accuracy | ΔRPS vs M0 [95% CI] |
|---|---|---|---|---|
| Market odds (de-vigged) | 0.20418 | 1.00264 | 50.26% | |
| M0 market + controls | 0.20453 | 1.00424 | 50.13% | 0 |
| M1 classical engines re-weighted | 0.20455 | 1.00435 | 50.11% | +0.000021 [-0.000002, +0.000043] |
| Engine 4 (Emergent Codex) | 0.20458 | 1.00442 | 50.11% | +0.000055 [-0.000012, +0.000124] |
| Engine 4, coin-flip frame (negative control) | 0.20464 | 1.00460 | 50.05% | +0.000000 [+0.000000, +0.000000] |

Note: M0 (market + calendar/scheduling controls) is itself slightly *worse* than the raw de-vigged odds (RPS 0.20453 vs 0.20418): the ~90 control covariates add a little noise. Engine 4 is benchmarked against M0 so that astrology is never credited with calendar effects. Since it does not beat M0, it falls further short of the raw market. The app therefore shows raw market probabilities whenever the Engine 4 gate is closed.

Per fold, inner validation chose: 2020/21: FAV, 8 primitives; 2021/22: FAV, 215 primitives; 2022/23: FAV, 0 primitives; 2023/24: FAV, 0 primitives; 2024/25: FAV, 0 primitives; 2025/26: FAV, 0 primitives; 2026/27: FAV, 0 primitives

## Raw accuracy of the classical engines (pre-vault, favourite frame)

| System | Accuracy | Picks favourite | Picks draw | n |
|---|---|---|---|---|
| Rao | 33.1% | 34.1% | 20.5% | 107,462 |
| Chokoisky | 32.9% | 33.5% | 16.8% | 107,462 |
| Frawley | 38.4% | 54.8% | 5.4% | 105,612 |
| Always favourite | 50.3% | 100.0% | 0.0% | 107,462 |
| Market (most likely outcome) | 50.3% | 99.9% | 0.1% | 107,462 |

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
| chokoisky.d1_cusp.Sa | 9,945 | 40.0% | 39.3% | +0.91 | 0.036 | 1.000 | not supported |
| rao.fans | 33,757 | 36.6% | 36.1% | +0.48 | 0.043 | 1.000 | not supported |
| chokoisky.d1_cusp.Ju | 9,753 | 36.9% | 37.6% | -0.87 | 0.049 | 1.000 | not supported |
| rao.score | 42,092 | 36.4% | 35.9% | +0.41 | 0.055 | 1.000 | not supported |
| chokoisky.d1_cusp.Ra | 7,638 | 36.4% | 37.2% | -0.94 | 0.058 | 1.000 | not supported |
| chokoisky.d1_cusp.Ke | 7,638 | 36.4% | 37.2% | -0.94 | 0.058 | 1.000 | not supported |
| chokoisky.tara.Wasat | 4,639 | 38.0% | 36.7% | +1.16 | 0.069 | 1.000 | not supported |
| chokoisky.victory_house | 87,386 | 33.3% | 33.1% | +0.22 | 0.129 | 1.000 | not supported |
| frawley.body.inside_enemy_house | 5,233 | 34.0% | 33.3% | +0.90 | 0.133 | 1.000 | not supported |
| chokoisky.tara.Spica | 4,359 | 37.3% | 38.0% | -0.98 | 0.136 | 1.000 | not supported |

## Codex

Version v2. Gate: closed (walk-forward ΔRPS vs market model: 95% CI does not exclude zero; placebo skies not yet run).

Vault (one-shot, 8,288 matches from 2025/26 onward, accessed 2026-10-27T20:54:03): ΔRPS +0.000000 [+0.000000, +0.000000].

| Status | Rule | Effect (pp) | q | Stability | Leagues | Placebo pct |
|---|---|---|---|---|---|---|
| — | The final model kept no primitive. | | | | | |

### Strongest single primitives (exploratory)

| Primitive | z | BH q | Placebo sd of z | Placebo pct |
|---|---|---|---|---|
| lord of the 10th (team1) in the 6th house (Campanus, lahiri) | +3.58 | 0.606 | — | — |
| lord of the 10th (team1) in the 7th house (Equal, lahiri) | -3.36 | 0.606 | — | — |
| lord of the 10th (team1) in the 6th house (Placidus, lahiri) | +3.35 | 0.606 | — | — |
| lord of the 7th (team2) in the 12th house (Campanus, lahiri) | -3.28 | 0.606 | — | — |
| lord of the 10th (team1) in the 7th house (Placidus, lahiri) | -3.20 | 0.606 | — | — |
| lord of the 10th (team1) in the 11th house (Campanus, lahiri) | +3.19 | 0.606 | — | — |
| Sun in the 12th house (Placidus) | -3.12 | 0.657 | — | — |
| Venus sextile Uranus | -3.07 | 0.657 | — | — |
| lord of the 10th (team1) in the 7th house (Regiomontanus, lahiri) | -3.05 | 0.657 | — | — |
| lord of the 10th (team1) just inside team2's Descendant (7th) (lahiri) | -2.98 | 0.657 | — | — |
| lord of the 10th (team1) in the 6th house (Regiomontanus, lahiri) | +2.95 | 0.657 | — | — |
| Uranus in the 11th house (Campanus) | -2.87 | 0.657 | — | — |
