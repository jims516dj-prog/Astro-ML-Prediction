# Live track record

_Updated 2026-11-14T18:43:48+00:00 · 773 settled · 130 pending · 950/950 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 773 | 0.1972 | 0.9466 | 56.1% | — |
| engine4 | 773 | 0.1980 | 0.9491 | 55.1% | +0.00087 [+0.00002, +0.00201] |
| synthesis | 773 | 0.1972 | 0.9466 | 56.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 773 | 31.6% | 33.4% | -1.9 ± 1.6 |
| chokoisky | 773 | 35.4% | 35.8% | -0.4 ± 1.6 |
| frawley | 758 | 38.9% | 37.9% | +1.0 ± 1.6 |
