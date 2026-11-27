# Findings

_Generated 2026-11-27T09:23:28 · lattice L-2026.2 · 108,788 matches · 2,563 astrological primitives_

## Headline

Across 68,381 out-of-sample matches (seasons 2020/21–2024/25), no combination of 2,563 astrological primitives improved on the market-based control model (ΔRPS +0.000017, 95% CI -0.000031 to +0.000064). No rule reached Provisional status.

## Walk-forward (seasons 2020/21–2024/25, out of sample)

ΔRPS is model minus market-based control model (M0); negative is better. 95% CI from a matchday block bootstrap.

| Model | RPS | Log loss | Accuracy | ΔRPS vs M0 [95% CI] |
|---|---|---|---|---|
| Market odds (de-vigged) | 0.20408 | 1.00163 | 50.35% | |
| M0 market + controls | 0.20441 | 1.00320 | 50.23% | 0 |
| M1 classical engines re-weighted | 0.20444 | 1.00332 | 50.22% | +0.000024 [+0.000000, +0.000048] |
| Engine 4 (Emergent Codex) | 0.20443 | 1.00325 | 50.24% | +0.000017 [-0.000031, +0.000064] |
| Engine 4, coin-flip frame (negative control) | 0.20455 | 1.00368 | 50.14% | +0.000000 [+0.000000, +0.000000] |

Note: M0 (market + calendar/scheduling controls) is itself slightly *worse* than the raw de-vigged odds (RPS 0.20441 vs 0.20408): the ~90 control covariates add a little noise. Engine 4 is benchmarked against M0 so that astrology is never credited with calendar effects. Since it does not beat M0, it falls further short of the raw market. The app therefore shows raw market probabilities whenever the Engine 4 gate is closed.

Per fold, inner validation chose: 2020/21: FAV, 4 primitives; 2021/22: FAV, 180 primitives; 2022/23: FAV, 0 primitives; 2023/24: FAV, 0 primitives; 2024/25: FAV, 0 primitives; 2025/26: FAV, 0 primitives; 2026/27: FAV, 0 primitives

## Raw accuracy of the classical engines (pre-vault, favourite frame)

| System | Accuracy | Picks favourite | Picks draw | n |
|---|---|---|---|---|
| Rao | 33.1% | 34.0% | 20.7% | 108,788 |
| Chokoisky | 32.9% | 33.6% | 16.9% | 108,788 |
| Frawley | 38.4% | 54.6% | 5.4% | 106,917 |
| Always favourite | 50.4% | 100.0% | 0.0% | 108,788 |
| Market (most likely outcome) | 50.4% | 99.9% | 0.1% | 108,788 |

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

## Doctrine Tribunal

Verdicts: not supported: 74

Ten strongest doctrines by raw p-value (still subject to Holm correction across all of them):

| Doctrine | Matches | Hit rate | Market expected | Effect (pp) | p | p (Holm) | Verdict |
|---|---|---|---|---|---|---|---|
| chokoisky.d1_cusp.Sa | 10,018 | 40.0% | 39.2% | +0.95 | 0.029 | 1.000 | not supported |
| chokoisky.d1_cusp.Ke | 7,707 | 36.3% | 37.2% | -1.05 | 0.033 | 1.000 | not supported |
| chokoisky.d1_cusp.Ra | 7,707 | 36.3% | 37.2% | -1.05 | 0.033 | 1.000 | not supported |
| rao.score | 42,335 | 36.5% | 36.0% | +0.41 | 0.052 | 1.000 | not supported |
| rao.fans | 33,953 | 36.5% | 36.0% | +0.45 | 0.056 | 1.000 | not supported |
| chokoisky.tara.Wasat | 4,688 | 38.1% | 36.7% | +1.12 | 0.078 | 1.000 | not supported |
| frawley.body.inside_enemy_house | 5,267 | 34.1% | 33.3% | +0.97 | 0.103 | 1.000 | not supported |
| chokoisky.d1_cusp.Ju | 9,818 | 37.0% | 37.7% | -0.72 | 0.103 | 1.000 | not supported |
| chokoisky.d1_cusp.Ve | 9,312 | 38.6% | 37.8% | +0.72 | 0.109 | 1.000 | not supported |
| chokoisky.victory_house | 88,464 | 33.3% | 33.1% | +0.22 | 0.128 | 1.000 | not supported |

## Codex

Version v3. Gate: closed (walk-forward ΔRPS vs market model: 95% CI does not exclude zero; placebo skies not yet run).

Vault (one-shot, 8,288 matches from 2025/26 onward, accessed 2026-10-27T20:54:03): ΔRPS +0.000000 [+0.000000, +0.000000].

| Status | Rule | Effect (pp) | q | Stability | Leagues | Placebo pct |
|---|---|---|---|---|---|---|
| candidate | When lord of the 10th (the favourite) in the 6th house (Campanus, lahiri), the favourite's win probability rises 1.2 pp relative to the market. | +1.20 | 0.346 | 0.1 | 8/10 | — |

### Strongest single primitives (exploratory)

| Primitive | z | BH q | Placebo sd of z | Placebo pct |
|---|---|---|---|---|
| lord of the 10th (team1) in the 6th house (Campanus, lahiri) | +3.82 | 0.346 | — | — |
| lord of the 10th (team1) in the 6th house (Placidus, lahiri) | +3.41 | 0.609 | — | — |
| lord of the 7th (team2) in the 12th house (Campanus, lahiri) | -3.38 | 0.609 | — | — |
| lord of the 10th (team1) in the 7th house (Equal, lahiri) | -3.22 | 0.710 | — | — |
| lord of the 10th (team1) in the 6th house (Regiomontanus, lahiri) | +3.14 | 0.710 | — | — |
| lord of the 10th (team1) in the 11th house (Campanus, lahiri) | +3.08 | 0.710 | — | — |
| Venus sextile Uranus | -3.07 | 0.710 | — | — |
| lord of the 10th (team1) in the 7th house (Placidus, lahiri) | -3.04 | 0.710 | — | — |
| Uranus in the 11th house (Campanus) | -3.02 | 0.710 | — | — |
| lord of the 7th (team2) in the 12th house (Placidus, lahiri) | -2.99 | 0.711 | — | — |
| lord of the 10th (team1) in the 7th house (Regiomontanus, lahiri) | -2.94 | 0.711 | — | — |
| lord of the 10th (team1) in the 2nd house (Regiomontanus, lahiri) | -2.88 | 0.711 | — | — |
