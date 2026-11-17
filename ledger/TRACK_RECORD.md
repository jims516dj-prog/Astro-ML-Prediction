# Live track record

_Updated 2026-11-17T03:51:28+00:00 · 904 settled · 61 pending · 1025/1025 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 904 | 0.1942 | 0.9342 | 57.3% | — |
| engine4 | 904 | 0.1949 | 0.9364 | 56.4% | +0.00075 [-0.00007, +0.00178] |
| synthesis | 904 | 0.1942 | 0.9342 | 57.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 904 | 30.8% | 32.7% | -2.0 ± 1.4 |
| chokoisky | 904 | 34.7% | 35.7% | -1.0 ± 1.5 |
| frawley | 887 | 38.4% | 36.8% | +1.7 ± 1.5 |
