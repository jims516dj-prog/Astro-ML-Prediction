# Live track record

_Updated 2026-11-13T13:12:41+00:00 · 636 settled · 188 pending · 869/869 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 636 | 0.1982 | 0.9520 | 55.7% | — |
| engine4 | 636 | 0.1993 | 0.9550 | 54.4% | +0.00106 [-0.00008, +0.00241] |
| synthesis | 636 | 0.1982 | 0.9520 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 636 | 33.3% | 34.1% | -0.8 ± 1.7 |
| chokoisky | 636 | 35.7% | 35.7% | -0.1 ± 1.8 |
| frawley | 625 | 40.3% | 38.5% | +1.8 ± 1.8 |
