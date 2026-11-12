# Live track record

_Updated 2026-11-12T09:43:48+00:00 · 575 settled · 79 pending · 674/674 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 575 | 0.2026 | 0.9591 | 55.5% | — |
| engine4 | 575 | 0.2038 | 0.9625 | 54.1% | +0.00117 [-0.00012, +0.00258] |
| synthesis | 575 | 0.2026 | 0.9591 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 575 | 34.6% | 34.5% | +0.1 ± 1.8 |
| chokoisky | 575 | 34.4% | 35.0% | -0.6 ± 1.9 |
| frawley | 565 | 41.1% | 38.2% | +2.8 ± 1.9 |
