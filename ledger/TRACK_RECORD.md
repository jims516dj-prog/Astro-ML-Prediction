# Live track record

_Updated 2026-11-03T22:21:09+00:00 · 228 settled · 17 pending · 245/245 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 228 | 0.2074 | 0.9661 | 57.0% | — |
| engine4 | 228 | 0.2104 | 0.9746 | 53.5% | +0.00296 [+0.00019, +0.00417] |
| synthesis | 228 | 0.2074 | 0.9661 | 57.0% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 228 | 37.7% | 36.4% | +1.3 ± 3.0 |
| chokoisky | 228 | 38.2% | 37.8% | +0.4 ± 3.0 |
| frawley | 221 | 40.3% | 37.3% | +2.9 ± 3.0 |
