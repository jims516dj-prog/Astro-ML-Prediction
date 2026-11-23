# Live track record

_Updated 2026-11-23T16:06:36+00:00 · 1307 settled · 137 pending · 1517/1517 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1307 | 0.2000 | 0.9532 | 55.2% | — |
| engine4 | 1307 | 0.2005 | 0.9547 | 54.6% | +0.00052 [-0.00005, +0.00128] |
| synthesis | 1307 | 0.2000 | 0.9532 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1307 | 29.9% | 31.5% | -1.5 ± 1.2 |
| chokoisky | 1307 | 34.9% | 36.0% | -1.1 ± 1.2 |
| frawley | 1285 | 39.6% | 37.2% | +2.5 ± 1.2 |
