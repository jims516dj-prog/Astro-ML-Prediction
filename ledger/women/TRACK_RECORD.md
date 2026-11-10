# Live track record

_Updated 2026-11-10T22:28:13+00:00 · 4 settled · 8 pending · 12/12 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 4 | 0.1462 | 0.8746 | 75.0% | — |
| engine4 | 4 | 0.1462 | 0.8746 | 75.0% | needs n ≥ 30 |
| synthesis | 4 | 0.1462 | 0.8746 | 75.0% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 4 | 0.0% | 15.3% | -15.3 ± 17.7 |
| chokoisky | 4 | 0.0% | 33.7% | -33.7 ± 19.2 |
| frawley | 4 | 25.0% | 28.3% | -3.3 ± 19.2 |
