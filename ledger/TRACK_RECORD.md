# Live track record

_Updated 2026-11-26T03:10:56+00:00 · 1474 settled · 94 pending · 1654/1654 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1474 | 0.2001 | 0.9541 | 55.2% | — |
| engine4 | 1474 | 0.2005 | 0.9554 | 54.7% | +0.00046 [-0.00004, +0.00114] |
| synthesis | 1474 | 0.2001 | 0.9541 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1474 | 30.9% | 32.0% | -1.2 ± 1.1 |
| chokoisky | 1474 | 35.1% | 36.4% | -1.3 ± 1.2 |
| frawley | 1448 | 39.0% | 36.8% | +2.1 ± 1.2 |
