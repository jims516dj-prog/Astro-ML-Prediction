# Live track record

_Updated 2026-11-23T07:51:03+00:00 · 1306 settled · 135 pending · 1514/1514 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1306 | 0.1999 | 0.9526 | 55.3% | — |
| engine4 | 1306 | 0.2004 | 0.9541 | 54.7% | +0.00052 [-0.00005, +0.00128] |
| synthesis | 1306 | 0.1999 | 0.9526 | 55.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1306 | 29.9% | 31.4% | -1.5 ± 1.2 |
| chokoisky | 1306 | 34.9% | 35.9% | -1.0 ± 1.2 |
| frawley | 1284 | 39.6% | 37.2% | +2.5 ± 1.2 |
