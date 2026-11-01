# Live track record

_Updated 2026-11-01T11:53:14+00:00 · 19 settled · 196 pending · 215/215 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 19 | 0.2038 | 1.0977 | 47.4% | — |
| engine4 | 19 | 0.2034 | 1.0906 | 47.4% | needs n ≥ 30 |
| synthesis | 19 | 0.2038 | 1.0977 | 47.4% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 19 | 15.8% | 23.9% | -8.1 ± 9.6 |
| chokoisky | 19 | 36.8% | 36.1% | +0.7 ± 10.4 |
| frawley | 19 | 36.8% | 50.4% | -13.5 ± 11.1 |
