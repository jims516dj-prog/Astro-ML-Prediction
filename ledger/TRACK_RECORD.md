# Live track record

_Updated 2026-11-21T22:15:57+00:00 · 1172 settled · 195 pending · 1440/1440 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1172 | 0.2001 | 0.9549 | 55.2% | — |
| engine4 | 1172 | 0.2007 | 0.9566 | 54.5% | +0.00058 [-0.00002, +0.00137] |
| synthesis | 1172 | 0.2001 | 0.9549 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1172 | 29.0% | 31.0% | -2.0 ± 1.3 |
| chokoisky | 1172 | 34.8% | 35.8% | -1.0 ± 1.3 |
| frawley | 1150 | 39.4% | 36.6% | +2.8 ± 1.3 |
