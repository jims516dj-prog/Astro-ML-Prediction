# Live track record

_Updated 2026-11-24T03:23:41+00:00 · 1343 settled · 129 pending · 1554/1554 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1343 | 0.2006 | 0.9545 | 55.0% | — |
| engine4 | 1343 | 0.2011 | 0.9560 | 54.4% | +0.00050 [-0.00004, +0.00124] |
| synthesis | 1343 | 0.2006 | 0.9545 | 55.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1343 | 30.2% | 31.7% | -1.5 ± 1.2 |
| chokoisky | 1343 | 34.8% | 35.9% | -1.1 ± 1.2 |
| frawley | 1320 | 39.6% | 37.2% | +2.4 ± 1.2 |
