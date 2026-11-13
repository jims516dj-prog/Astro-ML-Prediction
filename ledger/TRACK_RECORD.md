# Live track record

_Updated 2026-11-13T22:42:27+00:00 · 700 settled · 141 pending · 888/888 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 700 | 0.1987 | 0.9511 | 55.7% | — |
| engine4 | 700 | 0.1997 | 0.9539 | 54.6% | +0.00096 [-0.00007, +0.00227] |
| synthesis | 700 | 0.1987 | 0.9511 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 700 | 32.3% | 33.6% | -1.3 ± 1.6 |
| chokoisky | 700 | 36.0% | 36.0% | -0.0 ± 1.7 |
| frawley | 688 | 39.5% | 38.5% | +1.0 ± 1.7 |
