# Live track record

_Updated 2026-11-12T03:46:12+00:00 · 10 settled · 6 pending · 16/16 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 10 | 0.1120 | 0.7530 | 70.0% | — |
| engine4 | 10 | 0.1120 | 0.7530 | 70.0% | needs n ≥ 30 |
| synthesis | 10 | 0.1120 | 0.7530 | 70.0% | needs n ≥ 30 |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 10 | 0.0% | 16.4% | -16.4 ± 11.4 |
| chokoisky | 10 | 10.0% | 35.9% | -25.9 ± 12.4 |
| frawley | 9 | 44.4% | 42.1% | +2.4 ± 13.5 |
