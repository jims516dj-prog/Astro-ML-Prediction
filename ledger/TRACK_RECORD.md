# Live track record

_Updated 2026-11-19T23:40:54+00:00 · 958 settled · 76 pending · 1100/1100 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 958 | 0.1935 | 0.9339 | 57.0% | — |
| engine4 | 958 | 0.1942 | 0.9359 | 56.2% | +0.00070 [-0.00005, +0.00161] |
| synthesis | 958 | 0.1935 | 0.9339 | 57.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 958 | 30.5% | 32.1% | -1.7 ± 1.4 |
| chokoisky | 958 | 35.1% | 35.7% | -0.6 ± 1.4 |
| frawley | 941 | 38.4% | 36.9% | +1.4 ± 1.4 |
