# Live track record

_Updated 2026-11-13T10:45:34+00:00 · 15 settled · 41 pending · 56/56 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 15 | 0.1205 | 0.7689 | 73.3% | — |
| engine4 | 15 | 0.1205 | 0.7689 | 73.3% | needs n ≥ 30 |
| synthesis | 15 | 0.1205 | 0.7689 | 73.3% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 15 | 6.7% | 19.9% | -13.3 ± 9.7 |
| chokoisky | 15 | 26.7% | 36.7% | -10.1 ± 10.4 |
| frawley | 14 | 35.7% | 42.7% | -7.0 ± 10.9 |
