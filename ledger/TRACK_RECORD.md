# Live track record

_Updated 2026-11-09T23:33:26+00:00 · 521 settled · 57 pending · 589/589 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 521 | 0.2021 | 0.9551 | 55.7% | — |
| engine4 | 521 | 0.2034 | 0.9588 | 54.1% | +0.00129 [-0.00012, +0.00266] |
| synthesis | 521 | 0.2021 | 0.9551 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 521 | 34.9% | 35.2% | -0.3 ± 1.9 |
| chokoisky | 521 | 34.0% | 34.9% | -0.9 ± 2.0 |
| frawley | 511 | 41.3% | 38.4% | +2.8 ± 2.0 |
