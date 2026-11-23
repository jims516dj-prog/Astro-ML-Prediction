# Live track record

_Updated 2026-11-23T22:50:04+00:00 · 1336 settled · 101 pending · 1519/1519 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1336 | 0.2003 | 0.9527 | 55.2% | — |
| engine4 | 1336 | 0.2008 | 0.9542 | 54.6% | +0.00050 [-0.00005, +0.00127] |
| synthesis | 1336 | 0.2003 | 0.9527 | 55.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1336 | 30.4% | 31.7% | -1.3 ± 1.2 |
| chokoisky | 1336 | 34.9% | 36.0% | -1.1 ± 1.2 |
| frawley | 1313 | 39.7% | 37.2% | +2.5 ± 1.2 |
