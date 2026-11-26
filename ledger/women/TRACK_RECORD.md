# Live track record

_Updated 2026-11-26T15:24:54+00:00 · 96 settled · 3 pending · 109/109 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 96 | 0.1746 | 0.8908 | 63.5% | — |
| engine4 | 96 | 0.1746 | 0.8908 | 63.5% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 96 | 0.1746 | 0.8908 | 63.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 96 | 28.1% | 29.9% | -1.8 ± 4.2 |
| chokoisky | 96 | 34.4% | 40.3% | -5.9 ± 4.3 |
| frawley | 93 | 30.1% | 33.1% | -3.0 ± 4.2 |
