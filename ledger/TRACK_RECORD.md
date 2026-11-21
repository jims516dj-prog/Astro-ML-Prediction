# Live track record

_Updated 2026-11-21T13:33:53+00:00 · 1027 settled · 331 pending · 1427/1427 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1027 | 0.1972 | 0.9481 | 55.9% | — |
| engine4 | 1027 | 0.1979 | 0.9499 | 55.1% | +0.00066 [-0.00002, +0.00144] |
| synthesis | 1027 | 0.1972 | 0.9481 | 55.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1027 | 29.9% | 31.7% | -1.8 ± 1.3 |
| chokoisky | 1027 | 34.8% | 35.9% | -1.2 ± 1.4 |
| frawley | 1009 | 38.2% | 36.6% | +1.5 ± 1.4 |
