# Live track record

_Updated 2026-11-03T05:02:16+00:00 · 199 settled · 16 pending · 215/215 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 199 | 0.2067 | 0.9627 | 58.8% | — |
| engine4 | 199 | 0.2103 | 0.9723 | 54.8% | +0.00362 [+0.00181, +0.00496] |
| synthesis | 199 | 0.2067 | 0.9627 | 58.8% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 199 | 38.7% | 37.7% | +1.0 ± 3.2 |
| chokoisky | 199 | 37.7% | 37.1% | +0.6 ± 3.2 |
| frawley | 192 | 40.6% | 36.6% | +4.0 ± 3.2 |
