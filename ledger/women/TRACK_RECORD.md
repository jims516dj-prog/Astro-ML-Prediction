# Live track record

_Updated 2026-11-11T23:32:59+00:00 · 9 settled · 5 pending · 14/14 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 9 | 0.1236 | 0.8223 | 66.7% | — |
| engine4 | 9 | 0.1236 | 0.8223 | 66.7% | needs n ≥ 30 |
| synthesis | 9 | 0.1236 | 0.8223 | 66.7% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 9 | 0.0% | 17.7% | -17.7 ± 12.4 |
| chokoisky | 9 | 0.0% | 30.1% | -30.1 ± 13.2 |
| frawley | 8 | 50.0% | 46.8% | +3.2 ± 15.0 |
