# Live track record

_Updated 2026-11-24T13:40:17+00:00 · 1374 settled · 116 pending · 1572/1572 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1374 | 0.2006 | 0.9549 | 55.2% | — |
| engine4 | 1374 | 0.2011 | 0.9563 | 54.6% | +0.00049 [-0.00004, +0.00123] |
| synthesis | 1374 | 0.2006 | 0.9549 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1374 | 30.1% | 31.7% | -1.6 ± 1.2 |
| chokoisky | 1374 | 35.1% | 36.0% | -0.9 ± 1.2 |
| frawley | 1349 | 39.6% | 37.3% | +2.3 ± 1.2 |
