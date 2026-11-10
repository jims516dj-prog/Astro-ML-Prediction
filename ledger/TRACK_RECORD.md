# Live track record

_Updated 2026-11-10T04:58:32+00:00 · 524 settled · 54 pending · 596/596 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 524 | 0.2020 | 0.9554 | 55.7% | — |
| engine4 | 524 | 0.2032 | 0.9591 | 54.2% | +0.00129 [-0.00013, +0.00273] |
| synthesis | 524 | 0.2020 | 0.9554 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 524 | 34.7% | 35.1% | -0.4 ± 1.9 |
| chokoisky | 524 | 34.2% | 34.9% | -0.8 ± 1.9 |
| frawley | 514 | 41.2% | 38.5% | +2.7 ± 2.0 |
