# Live track record

_Updated 2026-11-07T16:56:09+00:00 · 338 settled · 212 pending · 559/559 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 338 | 0.2062 | 0.9627 | 56.2% | — |
| engine4 | 338 | 0.2082 | 0.9683 | 53.8% | +0.00199 [-0.00009, +0.00320] |
| synthesis | 338 | 0.2062 | 0.9627 | 56.2% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 338 | 36.1% | 34.8% | +1.3 ± 2.4 |
| chokoisky | 338 | 34.3% | 35.6% | -1.3 ± 2.4 |
| frawley | 329 | 42.2% | 38.7% | +3.5 ± 2.5 |
