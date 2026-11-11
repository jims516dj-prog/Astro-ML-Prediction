# Live track record

_Updated 2026-11-11T18:06:53+00:00 · 569 settled · 43 pending · 632/632 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 569 | 0.2022 | 0.9583 | 55.5% | — |
| engine4 | 569 | 0.2034 | 0.9617 | 54.1% | +0.00118 [-0.00008, +0.00250] |
| synthesis | 569 | 0.2022 | 0.9583 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 569 | 34.8% | 34.7% | +0.1 ± 1.9 |
| chokoisky | 569 | 34.4% | 35.0% | -0.6 ± 1.9 |
| frawley | 559 | 41.1% | 38.4% | +2.8 ± 1.9 |
