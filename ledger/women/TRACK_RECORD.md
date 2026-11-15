# Live track record

_Updated 2026-11-15T12:49:10+00:00 · 49 settled · 29 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 49 | 0.1647 | 0.8481 | 69.4% | — |
| engine4 | 49 | 0.1647 | 0.8481 | 69.4% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 49 | 0.1647 | 0.8481 | 69.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 49 | 32.7% | 33.5% | -0.8 ± 5.9 |
| chokoisky | 49 | 24.5% | 35.4% | -10.9 ± 5.9 |
| frawley | 47 | 36.2% | 32.8% | +3.4 ± 5.9 |
