# Live track record

_Updated 2026-11-26T14:14:52+00:00 · 1479 settled · 95 pending · 1660/1660 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1479 | 0.1997 | 0.9530 | 55.3% | — |
| engine4 | 1479 | 0.2002 | 0.9543 | 54.8% | +0.00046 [-0.00004, +0.00114] |
| synthesis | 1479 | 0.1997 | 0.9530 | 55.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1479 | 30.9% | 32.1% | -1.2 ± 1.1 |
| chokoisky | 1479 | 35.2% | 36.4% | -1.3 ± 1.1 |
| frawley | 1453 | 39.0% | 36.9% | +2.2 ± 1.2 |
