# Live track record

_Updated 2026-11-21T21:47:12+00:00 · 82 settled · 13 pending · 105/105 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 82 | 0.1642 | 0.8386 | 67.1% | — |
| engine4 | 82 | 0.1642 | 0.8386 | 67.1% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 82 | 0.1642 | 0.8386 | 67.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 82 | 25.6% | 29.9% | -4.3 ± 4.5 |
| chokoisky | 82 | 34.1% | 39.8% | -5.6 ± 4.7 |
| frawley | 79 | 31.6% | 31.6% | +0.1 ± 4.5 |
