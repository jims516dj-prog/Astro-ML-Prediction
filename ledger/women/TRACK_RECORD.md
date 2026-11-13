# Live track record

_Updated 2026-11-13T22:43:25+00:00 · 18 settled · 41 pending · 59/59 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 18 | 0.1480 | 0.8195 | 72.2% | — |
| engine4 | 18 | 0.1480 | 0.8195 | 72.2% | needs n ≥ 30 |
| synthesis | 18 | 0.1480 | 0.8195 | 72.2% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 18 | 11.1% | 19.4% | -8.3 ± 8.8 |
| chokoisky | 18 | 33.3% | 41.1% | -7.7 ± 9.8 |
| frawley | 17 | 41.2% | 40.2% | +1.0 ± 9.9 |
