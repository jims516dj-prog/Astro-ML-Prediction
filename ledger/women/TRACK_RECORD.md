# Live track record

_Updated 2026-11-12T13:15:25+00:00 · 11 settled · 31 pending · 42/42 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 11 | 0.1163 | 0.7474 | 72.7% | — |
| engine4 | 11 | 0.1163 | 0.7474 | 72.7% | needs n ≥ 30 |
| synthesis | 11 | 0.1163 | 0.7474 | 72.7% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 11 | 0.0% | 17.3% | -17.3 ± 11.1 |
| chokoisky | 11 | 9.1% | 34.8% | -25.7 ± 11.9 |
| frawley | 10 | 40.0% | 40.5% | -0.5 ± 12.9 |
