# Live track record

_Updated 2026-11-09T04:10:33+00:00 · 504 settled · 68 pending · 581/581 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 504 | 0.2010 | 0.9516 | 56.3% | — |
| engine4 | 504 | 0.2023 | 0.9554 | 54.8% | +0.00134 [-0.00013, +0.00269] |
| synthesis | 504 | 0.2010 | 0.9516 | 56.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 504 | 34.9% | 34.8% | +0.1 ± 2.0 |
| chokoisky | 504 | 33.7% | 34.9% | -1.2 ± 2.0 |
| frawley | 494 | 41.1% | 38.4% | +2.7 ± 2.0 |
