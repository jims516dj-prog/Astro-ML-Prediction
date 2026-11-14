# Live track record

_Updated 2026-11-14T12:19:13+00:00 · 25 settled · 49 pending · 74/74 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 25 | 0.1719 | 0.9016 | 64.0% | — |
| engine4 | 25 | 0.1719 | 0.9016 | 64.0% | needs n ≥ 30 |
| synthesis | 25 | 0.1719 | 0.9016 | 64.0% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 25 | 12.0% | 28.6% | -16.6 ± 7.6 |
| chokoisky | 25 | 32.0% | 41.9% | -9.9 ± 8.1 |
| frawley | 24 | 37.5% | 36.0% | +1.5 ± 7.9 |
