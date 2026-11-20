# Live track record

_Updated 2026-11-20T14:07:04+00:00 · 967 settled · 365 pending · 1399/1399 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 967 | 0.1945 | 0.9371 | 56.8% | — |
| engine4 | 967 | 0.1952 | 0.9390 | 55.9% | +0.00070 [-0.00002, +0.00164] |
| synthesis | 967 | 0.1945 | 0.9371 | 56.8% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 967 | 30.3% | 32.1% | -1.8 ± 1.4 |
| chokoisky | 967 | 34.9% | 35.7% | -0.8 ± 1.4 |
| frawley | 949 | 38.5% | 36.9% | +1.6 ± 1.4 |
