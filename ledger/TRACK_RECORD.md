# Live track record

_Updated 2026-11-07T20:58:10+00:00 · 383 settled · 169 pending · 561/561 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 383 | 0.2054 | 0.9651 | 55.6% | — |
| engine4 | 383 | 0.2072 | 0.9701 | 53.5% | +0.00176 [-0.00007, +0.00307] |
| synthesis | 383 | 0.2054 | 0.9651 | 55.6% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 383 | 35.5% | 34.9% | +0.6 ± 2.3 |
| chokoisky | 383 | 34.2% | 35.1% | -0.9 ± 2.3 |
| frawley | 373 | 41.6% | 38.7% | +2.9 ± 2.3 |
