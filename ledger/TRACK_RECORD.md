# Live track record

_Updated 2026-11-27T15:12:14+00:00 · 1527 settled · 334 pending · 1947/1947 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1527 | 0.2001 | 0.9523 | 55.5% | — |
| engine4 | 1527 | 0.2005 | 0.9535 | 55.0% | +0.00044 [-0.00003, +0.00106] |
| synthesis | 1527 | 0.2001 | 0.9523 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1527 | 31.3% | 32.3% | -1.0 ± 1.1 |
| chokoisky | 1527 | 35.3% | 36.5% | -1.2 ± 1.1 |
| frawley | 1499 | 38.8% | 36.7% | +2.1 ± 1.1 |
