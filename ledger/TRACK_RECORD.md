# Live track record

_Updated 2026-11-10T13:55:43+00:00 · 553 settled · 26 pending · 599/599 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 553 | 0.2036 | 0.9664 | 55.2% | — |
| engine4 | 553 | 0.2048 | 0.9699 | 53.7% | +0.00122 [-0.00012, +0.00269] |
| synthesis | 553 | 0.2036 | 0.9664 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 553 | 35.1% | 35.0% | +0.0 ± 1.9 |
| chokoisky | 553 | 34.0% | 34.9% | -0.9 ± 1.9 |
| frawley | 543 | 40.7% | 38.4% | +2.3 ± 1.9 |
