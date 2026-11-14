# Live track record

_Updated 2026-11-14T21:34:12+00:00 · 792 settled · 112 pending · 951/951 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 792 | 0.1979 | 0.9464 | 56.2% | — |
| engine4 | 792 | 0.1987 | 0.9489 | 55.2% | +0.00085 [+0.00002, +0.00199] |
| synthesis | 792 | 0.1979 | 0.9464 | 56.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 792 | 31.1% | 33.2% | -2.1 ± 1.5 |
| chokoisky | 792 | 36.0% | 35.9% | +0.1 ± 1.6 |
| frawley | 777 | 38.6% | 37.6% | +1.0 ± 1.6 |
