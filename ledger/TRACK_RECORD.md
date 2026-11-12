# Live track record

_Updated 2026-11-12T07:29:07+00:00 · 574 settled · 69 pending · 663/663 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 574 | 0.2029 | 0.9603 | 55.4% | — |
| engine4 | 574 | 0.2040 | 0.9636 | 54.0% | +0.00117 [-0.00012, +0.00258] |
| synthesis | 574 | 0.2029 | 0.9603 | 55.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 574 | 34.7% | 34.5% | +0.1 ± 1.8 |
| chokoisky | 574 | 34.5% | 35.1% | -0.6 ± 1.9 |
| frawley | 564 | 41.1% | 38.3% | +2.9 ± 1.9 |
