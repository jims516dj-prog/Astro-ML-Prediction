# Live track record

_Updated 2026-11-15T12:48:54+00:00 · 828 settled · 101 pending · 977/977 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 828 | 0.1973 | 0.9441 | 56.4% | — |
| engine4 | 828 | 0.1981 | 0.9465 | 55.4% | +0.00081 [-0.00005, +0.00197] |
| synthesis | 828 | 0.1973 | 0.9441 | 56.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 828 | 31.0% | 33.1% | -2.1 ± 1.5 |
| chokoisky | 828 | 35.4% | 35.7% | -0.3 ± 1.5 |
| frawley | 813 | 38.5% | 37.2% | +1.3 ± 1.5 |
