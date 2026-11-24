# Live track record

_Updated 2026-11-24T15:58:48+00:00 · 1378 settled · 114 pending · 1574/1574 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1378 | 0.2008 | 0.9557 | 55.1% | — |
| engine4 | 1378 | 0.2013 | 0.9571 | 54.5% | +0.00049 [-0.00004, +0.00122] |
| synthesis | 1378 | 0.2008 | 0.9557 | 55.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1378 | 30.1% | 31.8% | -1.7 ± 1.2 |
| chokoisky | 1378 | 35.0% | 36.0% | -1.0 ± 1.2 |
| frawley | 1353 | 39.6% | 37.3% | +2.3 ± 1.2 |
