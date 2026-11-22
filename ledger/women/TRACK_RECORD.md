# Live track record

_Updated 2026-11-22T13:28:16+00:00 · 86 settled · 9 pending · 105/105 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 86 | 0.1642 | 0.8466 | 65.1% | — |
| engine4 | 86 | 0.1642 | 0.8466 | 65.1% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 86 | 0.1642 | 0.8466 | 65.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 86 | 25.6% | 29.4% | -3.8 ± 4.4 |
| chokoisky | 86 | 33.7% | 40.4% | -6.7 ± 4.6 |
| frawley | 83 | 30.1% | 31.9% | -1.7 ± 4.4 |
