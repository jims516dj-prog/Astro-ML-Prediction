# Live track record

_Updated 2026-11-26T21:59:47+00:00 · 1503 settled · 73 pending · 1662/1662 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1503 | 0.1999 | 0.9519 | 55.5% | — |
| engine4 | 1503 | 0.2003 | 0.9532 | 55.0% | +0.00045 [-0.00004, +0.00114] |
| synthesis | 1503 | 0.1999 | 0.9519 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1503 | 31.2% | 32.4% | -1.2 ± 1.1 |
| chokoisky | 1503 | 35.1% | 36.4% | -1.4 ± 1.1 |
| frawley | 1476 | 39.1% | 36.8% | +2.3 ± 1.1 |
