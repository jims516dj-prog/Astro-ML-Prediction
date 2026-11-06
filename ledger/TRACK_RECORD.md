# Live track record

_Updated 2026-11-06T22:10:41+00:00 · 298 settled · 248 pending · 555/555 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 298 | 0.2065 | 0.9636 | 56.7% | — |
| engine4 | 298 | 0.2088 | 0.9701 | 54.0% | +0.00226 [-0.00010, +0.00345] |
| synthesis | 298 | 0.2065 | 0.9636 | 56.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 298 | 35.9% | 34.0% | +1.9 ± 2.6 |
| chokoisky | 298 | 35.9% | 36.0% | -0.1 ± 2.6 |
| frawley | 289 | 42.2% | 38.7% | +3.5 ± 2.6 |
