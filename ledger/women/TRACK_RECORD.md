# Live track record

_Updated 2026-11-16T06:22:22+00:00 · 69 settled · 4 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 69 | 0.1686 | 0.8695 | 63.8% | — |
| engine4 | 69 | 0.1686 | 0.8695 | 63.8% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 69 | 0.1686 | 0.8695 | 63.8% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 69 | 29.0% | 31.3% | -2.4 ± 5.0 |
| chokoisky | 69 | 30.4% | 38.6% | -8.1 ± 5.1 |
| frawley | 66 | 33.3% | 30.8% | +2.5 ± 5.0 |
