# Live track record

_Updated 2026-11-26T01:05:20+00:00 · 1468 settled · 100 pending · 1654/1654 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1468 | 0.2004 | 0.9548 | 55.2% | — |
| engine4 | 1468 | 0.2009 | 0.9561 | 54.6% | +0.00046 [-0.00004, +0.00113] |
| synthesis | 1468 | 0.2004 | 0.9548 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1468 | 31.0% | 32.1% | -1.1 ± 1.1 |
| chokoisky | 1468 | 35.0% | 36.3% | -1.3 ± 1.2 |
| frawley | 1442 | 38.9% | 36.8% | +2.2 ± 1.2 |
