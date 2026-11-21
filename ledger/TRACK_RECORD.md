# Live track record

_Updated 2026-11-21T21:47:01+00:00 · 1158 settled · 209 pending · 1440/1440 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1158 | 0.2000 | 0.9539 | 55.5% | — |
| engine4 | 1158 | 0.2006 | 0.9556 | 54.8% | +0.00058 [-0.00002, +0.00137] |
| synthesis | 1158 | 0.2000 | 0.9539 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1158 | 28.9% | 31.1% | -2.2 ± 1.3 |
| chokoisky | 1158 | 34.9% | 35.7% | -0.9 ± 1.3 |
| frawley | 1136 | 39.3% | 36.6% | +2.8 ± 1.3 |
