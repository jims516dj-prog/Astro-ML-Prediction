# Live track record

_Updated 2026-11-19T14:31:34+00:00 · 73 settled · 4 pending · 87/87 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 73 | 0.1611 | 0.8365 | 65.8% | — |
| engine4 | 73 | 0.1611 | 0.8365 | 65.8% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 73 | 0.1611 | 0.8365 | 65.8% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 73 | 27.4% | 30.2% | -2.8 ± 4.8 |
| chokoisky | 73 | 34.2% | 40.6% | -6.4 ± 5.0 |
| frawley | 70 | 34.3% | 31.6% | +2.7 ± 4.8 |
