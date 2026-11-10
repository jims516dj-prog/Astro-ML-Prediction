# Live track record

_Updated 2026-11-10T02:05:30+00:00 · 523 settled · 55 pending · 596/596 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 523 | 0.2020 | 0.9543 | 55.8% | — |
| engine4 | 523 | 0.2033 | 0.9580 | 54.3% | +0.00129 [-0.00013, +0.00273] |
| synthesis | 523 | 0.2020 | 0.9543 | 55.8% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 523 | 34.8% | 35.2% | -0.4 ± 1.9 |
| chokoisky | 523 | 34.2% | 35.0% | -0.7 ± 1.9 |
| frawley | 513 | 41.3% | 38.5% | +2.8 ± 2.0 |
