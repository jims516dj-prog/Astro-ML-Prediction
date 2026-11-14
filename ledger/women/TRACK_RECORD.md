# Live track record

_Updated 2026-11-14T18:45:04+00:00 · 37 settled · 40 pending · 77/77 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 37 | 0.1632 | 0.8568 | 70.3% | — |
| engine4 | 37 | 0.1632 | 0.8568 | 70.3% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 37 | 0.1632 | 0.8568 | 70.3% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 37 | 29.7% | 34.8% | -5.1 ± 6.7 |
| chokoisky | 37 | 27.0% | 36.1% | -9.1 ± 6.7 |
| frawley | 35 | 37.1% | 34.7% | +2.4 ± 6.7 |
