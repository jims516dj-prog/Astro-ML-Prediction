# Live track record

_Updated 2026-11-14T06:28:56+00:00 · 21 settled · 51 pending · 72/72 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 21 | 0.1547 | 0.8940 | 66.7% | — |
| engine4 | 21 | 0.1547 | 0.8940 | 66.7% | needs n ≥ 30 |
| synthesis | 21 | 0.1547 | 0.8940 | 66.7% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 21 | 9.5% | 24.3% | -14.8 ± 8.3 |
| chokoisky | 21 | 33.3% | 45.2% | -11.9 ± 9.2 |
| frawley | 20 | 35.0% | 36.0% | -1.0 ± 8.9 |
