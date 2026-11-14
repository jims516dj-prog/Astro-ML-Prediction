# Live track record

_Updated 2026-11-14T21:34:38+00:00 · 41 settled · 37 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 41 | 0.1649 | 0.8453 | 70.7% | — |
| engine4 | 41 | 0.1649 | 0.8453 | 70.7% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 41 | 0.1649 | 0.8453 | 70.7% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 41 | 31.7% | 34.6% | -2.9 ± 6.4 |
| chokoisky | 41 | 26.8% | 36.3% | -9.5 ± 6.5 |
| frawley | 39 | 38.5% | 34.4% | +4.1 ± 6.4 |
