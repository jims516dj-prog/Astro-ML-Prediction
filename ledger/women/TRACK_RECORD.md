# Live track record

_Updated 2026-11-15T17:24:05+00:00 · 61 settled · 16 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 61 | 0.1663 | 0.8473 | 67.2% | — |
| engine4 | 61 | 0.1663 | 0.8473 | 67.2% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 61 | 0.1663 | 0.8473 | 67.2% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 61 | 31.1% | 32.2% | -1.1 ± 5.3 |
| chokoisky | 61 | 27.9% | 38.5% | -10.6 ± 5.4 |
| frawley | 59 | 33.9% | 30.3% | +3.6 ± 5.2 |
