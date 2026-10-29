# Live track record

_Updated 2026-10-29T11:35:48+00:00 · 17 settled · 2 pending · 19/19 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 17 | 0.2135 | 1.1163 | 47.1% | — |
| engine4 | 17 | 0.2136 | 1.1138 | 47.1% | needs n ≥ 30 |
| synthesis | 17 | 0.2135 | 1.1163 | 47.1% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 17 | 17.6% | 23.9% | -6.2 ± 10.1 |
| chokoisky | 17 | 35.3% | 37.5% | -2.2 ± 11.1 |
| frawley | 17 | 35.3% | 50.3% | -15.0 ± 11.7 |
