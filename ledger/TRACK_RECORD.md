# Live track record

_Updated 2026-11-14T12:18:50+00:00 · 725 settled · 174 pending · 946/946 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 725 | 0.1984 | 0.9494 | 55.9% | — |
| engine4 | 725 | 0.1993 | 0.9521 | 54.8% | +0.00093 [+0.00002, +0.00207] |
| synthesis | 725 | 0.1984 | 0.9494 | 55.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 725 | 32.0% | 33.7% | -1.7 ± 1.6 |
| chokoisky | 725 | 36.1% | 36.4% | -0.2 ± 1.6 |
| frawley | 711 | 40.1% | 38.6% | +1.5 ± 1.7 |
