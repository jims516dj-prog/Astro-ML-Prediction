# Live track record

_Updated 2026-11-21T22:16:07+00:00 · 83 settled · 12 pending · 105/105 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 83 | 0.1623 | 0.8289 | 67.5% | — |
| engine4 | 83 | 0.1623 | 0.8289 | 67.5% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 83 | 0.1623 | 0.8289 | 67.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 83 | 25.3% | 29.6% | -4.3 ± 4.5 |
| chokoisky | 83 | 34.9% | 40.5% | -5.5 ± 4.6 |
| frawley | 80 | 31.2% | 31.2% | +0.1 ± 4.5 |
