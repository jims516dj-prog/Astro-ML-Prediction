# Live track record

_Updated 2026-11-21T13:35:35+00:00 · 80 settled · 11 pending · 101/101 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 80 | 0.1643 | 0.8322 | 67.5% | — |
| engine4 | 80 | 0.1643 | 0.8322 | 67.5% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 80 | 0.1643 | 0.8322 | 67.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 80 | 26.2% | 29.5% | -3.3 ± 4.6 |
| chokoisky | 80 | 35.0% | 39.6% | -4.6 ± 4.8 |
| frawley | 77 | 31.2% | 31.3% | -0.1 ± 4.6 |
