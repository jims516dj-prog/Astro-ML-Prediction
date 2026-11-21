# Live track record

_Updated 2026-11-21T03:52:28+00:00 · 1008 settled · 342 pending · 1419/1419 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1008 | 0.1973 | 0.9440 | 56.4% | — |
| engine4 | 1008 | 0.1980 | 0.9459 | 55.7% | +0.00067 [-0.00002, +0.00146] |
| synthesis | 1008 | 0.1973 | 0.9440 | 56.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1008 | 29.5% | 31.8% | -2.3 ± 1.4 |
| chokoisky | 1008 | 35.2% | 35.9% | -0.7 ± 1.4 |
| frawley | 990 | 38.5% | 36.6% | +1.9 ± 1.4 |
