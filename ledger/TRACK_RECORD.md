# Live track record

_Updated 2026-11-20T06:50:29+00:00 · 962 settled · 223 pending · 1252/1252 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 962 | 0.1937 | 0.9338 | 57.0% | — |
| engine4 | 962 | 0.1944 | 0.9358 | 56.1% | +0.00070 [-0.00002, +0.00165] |
| synthesis | 962 | 0.1937 | 0.9338 | 57.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 962 | 30.4% | 32.1% | -1.8 ± 1.4 |
| chokoisky | 962 | 34.9% | 35.7% | -0.8 ± 1.4 |
| frawley | 944 | 38.5% | 36.9% | +1.5 ± 1.4 |
