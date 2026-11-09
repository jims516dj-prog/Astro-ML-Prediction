# Live track record

_Updated 2026-11-09T19:10:12+00:00 · 515 settled · 59 pending · 585/585 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 515 | 0.2017 | 0.9530 | 55.9% | — |
| engine4 | 515 | 0.2030 | 0.9567 | 54.4% | +0.00131 [-0.00013, +0.00267] |
| synthesis | 515 | 0.2017 | 0.9530 | 55.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 515 | 35.0% | 35.1% | -0.2 ± 2.0 |
| chokoisky | 515 | 33.8% | 34.9% | -1.2 ± 2.0 |
| frawley | 505 | 41.6% | 38.4% | +3.2 ± 2.0 |
