# Live track record

_Updated 2026-11-28T01:38:57+00:00 · 100 settled · 3 pending · 113/113 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 100 | 0.1701 | 0.8751 | 64.0% | — |
| engine4 | 100 | 0.1701 | 0.8751 | 64.0% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 100 | 0.1701 | 0.8751 | 64.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 100 | 28.0% | 29.2% | -1.2 ± 4.1 |
| chokoisky | 100 | 34.0% | 40.2% | -6.2 ± 4.2 |
| frawley | 97 | 32.0% | 34.6% | -2.6 ± 4.1 |
