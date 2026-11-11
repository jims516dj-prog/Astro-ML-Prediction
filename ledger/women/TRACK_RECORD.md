# Live track record

_Updated 2026-11-11T18:06:54+00:00 · 7 settled · 6 pending · 13/13 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 7 | 0.1308 | 0.8223 | 71.4% | — |
| engine4 | 7 | 0.1308 | 0.8223 | 71.4% | needs n ≥ 30 |
| synthesis | 7 | 0.1308 | 0.8223 | 71.4% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 7 | 0.0% | 19.1% | -19.1 ± 14.6 |
| chokoisky | 7 | 0.0% | 29.8% | -29.8 ± 15.2 |
| frawley | 6 | 50.0% | 38.4% | +11.6 ± 17.3 |
