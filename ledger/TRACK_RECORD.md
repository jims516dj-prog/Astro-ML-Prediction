# Live track record

_Updated 2026-11-10T01:48:27+00:00 · 522 settled · 56 pending · 596/596 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 522 | 0.2022 | 0.9552 | 55.7% | — |
| engine4 | 522 | 0.2035 | 0.9589 | 54.2% | +0.00129 [-0.00012, +0.00266] |
| synthesis | 522 | 0.2022 | 0.9552 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 522 | 34.9% | 35.2% | -0.3 ± 1.9 |
| chokoisky | 522 | 34.1% | 34.9% | -0.8 ± 2.0 |
| frawley | 512 | 41.2% | 38.4% | +2.8 ± 2.0 |
