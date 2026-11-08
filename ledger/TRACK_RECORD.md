# Live track record

_Updated 2026-11-08T15:22:27+00:00 · 438 settled · 115 pending · 562/562 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 438 | 0.2021 | 0.9528 | 57.1% | — |
| engine4 | 438 | 0.2037 | 0.9572 | 55.3% | +0.00154 [+0.00002, +0.00298] |
| synthesis | 438 | 0.2021 | 0.9528 | 57.1% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 438 | 35.4% | 35.5% | -0.1 ± 2.1 |
| chokoisky | 438 | 33.8% | 34.6% | -0.8 ± 2.1 |
| frawley | 428 | 42.1% | 39.1% | +2.9 ± 2.2 |
