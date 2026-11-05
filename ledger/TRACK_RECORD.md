# Live track record

_Updated 2026-11-05T22:42:16+00:00 · 271 settled · 32 pending · 312/312 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 271 | 0.2078 | 0.9680 | 56.5% | — |
| engine4 | 271 | 0.2103 | 0.9751 | 53.5% | +0.00249 [-0.00023, +0.00366] |
| synthesis | 271 | 0.2078 | 0.9680 | 56.5% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 271 | 36.9% | 34.7% | +2.2 ± 2.7 |
| chokoisky | 271 | 37.6% | 36.6% | +1.1 ± 2.7 |
| frawley | 263 | 41.4% | 38.2% | +3.2 ± 2.8 |
