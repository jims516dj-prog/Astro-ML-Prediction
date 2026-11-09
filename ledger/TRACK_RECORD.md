# Live track record

_Updated 2026-11-09T00:46:00+00:00 · 503 settled · 68 pending · 581/581 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 503 | 0.2004 | 0.9504 | 56.5% | — |
| engine4 | 503 | 0.2018 | 0.9542 | 54.9% | +0.00134 [+0.00001, +0.00282] |
| synthesis | 503 | 0.2004 | 0.9504 | 56.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 503 | 34.8% | 34.8% | -0.0 ± 2.0 |
| chokoisky | 503 | 33.8% | 34.9% | -1.1 ± 2.0 |
| frawley | 493 | 41.0% | 38.4% | +2.5 ± 2.0 |
