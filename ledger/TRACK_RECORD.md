# Live track record

_Updated 2026-11-26T15:24:45+00:00 · 1482 settled · 92 pending · 1660/1660 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1482 | 0.1998 | 0.9530 | 55.3% | — |
| engine4 | 1482 | 0.2003 | 0.9543 | 54.8% | +0.00045 [-0.00004, +0.00114] |
| synthesis | 1482 | 0.1998 | 0.9530 | 55.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1482 | 31.0% | 32.1% | -1.1 ± 1.1 |
| chokoisky | 1482 | 35.2% | 36.5% | -1.3 ± 1.1 |
| frawley | 1455 | 39.0% | 36.9% | +2.1 ± 1.2 |
