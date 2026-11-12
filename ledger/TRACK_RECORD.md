# Live track record

_Updated 2026-11-12T13:15:21+00:00 · 576 settled · 137 pending · 757/757 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 576 | 0.2023 | 0.9578 | 55.6% | — |
| engine4 | 576 | 0.2034 | 0.9612 | 54.2% | +0.00117 [-0.00012, +0.00257] |
| synthesis | 576 | 0.2023 | 0.9578 | 55.6% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 576 | 34.7% | 34.6% | +0.1 ± 1.8 |
| chokoisky | 576 | 34.4% | 35.0% | -0.6 ± 1.9 |
| frawley | 566 | 41.0% | 38.2% | +2.8 ± 1.9 |
