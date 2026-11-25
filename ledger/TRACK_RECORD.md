# Live track record

_Updated 2026-11-25T02:37:53+00:00 · 1429 settled · 98 pending · 1612/1612 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1429 | 0.2007 | 0.9562 | 54.9% | — |
| engine4 | 1429 | 0.2012 | 0.9576 | 54.3% | +0.00047 [-0.00004, +0.00119] |
| synthesis | 1429 | 0.2007 | 0.9562 | 54.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1429 | 30.6% | 31.8% | -1.2 ± 1.1 |
| chokoisky | 1429 | 34.8% | 36.3% | -1.5 ± 1.2 |
| frawley | 1404 | 39.3% | 36.9% | +2.4 ± 1.2 |
