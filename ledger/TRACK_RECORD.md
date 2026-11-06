# Live track record

_Updated 2026-11-06T13:01:04+00:00 · 274 settled · 271 pending · 554/554 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 274 | 0.2069 | 0.9636 | 56.9% | — |
| engine4 | 274 | 0.2094 | 0.9706 | 54.0% | +0.00246 [-0.00011, +0.00360] |
| synthesis | 274 | 0.2069 | 0.9636 | 56.9% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 274 | 36.5% | 34.5% | +2.0 ± 2.7 |
| chokoisky | 274 | 38.0% | 36.6% | +1.4 ± 2.7 |
| frawley | 266 | 41.7% | 38.4% | +3.3 ± 2.7 |
