# Live track record

_Updated 2026-11-22T22:35:19+00:00 · 95 settled · 1 pending · 106/106 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 95 | 0.1743 | 0.8913 | 63.2% | — |
| engine4 | 95 | 0.1743 | 0.8913 | 63.2% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 95 | 0.1743 | 0.8913 | 63.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 95 | 27.4% | 29.7% | -2.4 ± 4.2 |
| chokoisky | 95 | 33.7% | 40.2% | -6.6 ± 4.3 |
| frawley | 92 | 30.4% | 33.1% | -2.7 ± 4.2 |
