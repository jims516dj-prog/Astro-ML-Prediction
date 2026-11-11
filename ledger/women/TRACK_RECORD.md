# Live track record

_Updated 2026-11-11T12:48:43+00:00 · 6 settled · 7 pending · 13/13 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 6 | 0.1385 | 0.8805 | 66.7% | — |
| engine4 | 6 | 0.1385 | 0.8805 | 66.7% | needs n ≥ 30 |
| synthesis | 6 | 0.1385 | 0.8805 | 66.7% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 6 | 0.0% | 19.6% | -19.6 ± 15.8 |
| chokoisky | 6 | 0.0% | 32.0% | -32.0 ± 16.6 |
| frawley | 5 | 40.0% | 33.6% | +6.4 ± 18.3 |
