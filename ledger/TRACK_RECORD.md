# Live track record

_Updated 2026-11-20T21:04:20+00:00 · 975 settled · 358 pending · 1401/1401 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 975 | 0.1951 | 0.9377 | 56.7% | — |
| engine4 | 975 | 0.1958 | 0.9397 | 55.9% | +0.00069 [-0.00002, +0.00163] |
| synthesis | 975 | 0.1951 | 0.9377 | 56.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 975 | 30.1% | 32.0% | -2.0 ± 1.4 |
| chokoisky | 975 | 34.9% | 35.8% | -0.9 ± 1.4 |
| frawley | 957 | 38.5% | 36.8% | +1.6 ± 1.4 |
