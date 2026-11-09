# Live track record

_Updated 2026-11-09T06:58:24+00:00 · 505 settled · 68 pending · 582/582 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 505 | 0.2008 | 0.9523 | 56.2% | — |
| engine4 | 505 | 0.2022 | 0.9561 | 54.7% | +0.00133 [-0.00013, +0.00268] |
| synthesis | 505 | 0.2008 | 0.9523 | 56.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 505 | 34.9% | 34.8% | +0.1 ± 2.0 |
| chokoisky | 505 | 33.7% | 34.9% | -1.3 ± 2.0 |
| frawley | 495 | 41.0% | 38.4% | +2.6 ± 2.0 |
