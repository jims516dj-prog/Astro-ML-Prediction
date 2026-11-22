# Live track record

_Updated 2026-11-22T22:35:09+00:00 · 1281 settled · 105 pending · 1459/1459 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1281 | 0.2001 | 0.9534 | 55.2% | — |
| engine4 | 1281 | 0.2006 | 0.9549 | 54.6% | +0.00053 [-0.00003, +0.00132] |
| synthesis | 1281 | 0.2001 | 0.9534 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1281 | 29.7% | 31.3% | -1.5 ± 1.2 |
| chokoisky | 1281 | 34.9% | 35.9% | -1.0 ± 1.2 |
| frawley | 1259 | 39.4% | 37.1% | +2.3 ± 1.2 |
