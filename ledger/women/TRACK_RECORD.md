# Live track record

_Updated 2026-11-15T21:52:37+00:00 · 66 settled · 8 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 66 | 0.1691 | 0.8780 | 63.6% | — |
| engine4 | 66 | 0.1691 | 0.8780 | 63.6% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 66 | 0.1691 | 0.8780 | 63.6% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 66 | 30.3% | 31.6% | -1.3 ± 5.1 |
| chokoisky | 66 | 27.3% | 37.9% | -10.6 ± 5.2 |
| frawley | 63 | 33.3% | 30.3% | +3.1 ± 5.1 |
