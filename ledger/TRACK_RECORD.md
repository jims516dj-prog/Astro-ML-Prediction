# Live track record

_Updated 2026-11-23T00:44:30+00:00 · 1296 settled · 145 pending · 1514/1514 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1296 | 0.1999 | 0.9521 | 55.3% | — |
| engine4 | 1296 | 0.2004 | 0.9536 | 54.7% | +0.00052 [-0.00003, +0.00130] |
| synthesis | 1296 | 0.1999 | 0.9521 | 55.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1296 | 29.9% | 31.3% | -1.4 ± 1.2 |
| chokoisky | 1296 | 35.0% | 35.9% | -1.0 ± 1.2 |
| frawley | 1274 | 39.6% | 37.2% | +2.3 ± 1.2 |
