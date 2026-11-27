# Live track record

_Updated 2026-11-27T01:04:44+00:00 · 1523 settled · 180 pending · 1789/1789 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1523 | 0.1999 | 0.9523 | 55.5% | — |
| engine4 | 1523 | 0.2004 | 0.9535 | 55.0% | +0.00044 [-0.00004, +0.00111] |
| synthesis | 1523 | 0.1999 | 0.9523 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1523 | 31.2% | 32.3% | -1.1 ± 1.1 |
| chokoisky | 1523 | 35.3% | 36.5% | -1.2 ± 1.1 |
| frawley | 1496 | 38.8% | 36.7% | +2.2 ± 1.1 |
