# Live track record

_Updated 2026-11-14T14:35:09+00:00 · 731 settled · 170 pending · 948/948 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 731 | 0.1987 | 0.9516 | 55.7% | — |
| engine4 | 731 | 0.1997 | 0.9542 | 54.6% | +0.00092 [+0.00002, +0.00205] |
| synthesis | 731 | 0.1987 | 0.9516 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 731 | 32.0% | 33.8% | -1.7 ± 1.6 |
| chokoisky | 731 | 36.0% | 36.4% | -0.4 ± 1.6 |
| frawley | 717 | 39.9% | 38.5% | +1.4 ± 1.7 |
