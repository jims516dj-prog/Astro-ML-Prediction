# Live track record

_Updated 2026-11-10T22:26:59+00:00 · 565 settled · 15 pending · 600/600 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 565 | 0.2028 | 0.9599 | 55.4% | — |
| engine4 | 565 | 0.2039 | 0.9633 | 54.0% | +0.00119 [-0.00011, +0.00264] |
| synthesis | 565 | 0.2028 | 0.9599 | 55.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 565 | 35.0% | 34.7% | +0.3 ± 1.9 |
| chokoisky | 565 | 34.3% | 34.9% | -0.6 ± 1.9 |
| frawley | 555 | 41.1% | 38.4% | +2.7 ± 1.9 |
