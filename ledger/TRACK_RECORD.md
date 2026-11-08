# Live track record

_Updated 2026-11-08T21:15:13+00:00 · 497 settled · 56 pending · 562/562 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 497 | 0.2011 | 0.9517 | 56.5% | — |
| engine4 | 497 | 0.2025 | 0.9556 | 54.9% | +0.00136 [+0.00001, +0.00282] |
| synthesis | 497 | 0.2011 | 0.9517 | 56.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 497 | 35.0% | 35.0% | -0.0 ± 2.0 |
| chokoisky | 497 | 34.0% | 35.0% | -1.0 ± 2.0 |
| frawley | 487 | 41.3% | 38.6% | +2.7 ± 2.0 |
