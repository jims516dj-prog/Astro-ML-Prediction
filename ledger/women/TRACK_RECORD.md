# Live track record

_Updated 2026-11-20T23:10:50+00:00 · 77 settled · 8 pending · 95/95 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 77 | 0.1577 | 0.8176 | 67.5% | — |
| engine4 | 77 | 0.1577 | 0.8176 | 67.5% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 77 | 0.1577 | 0.8176 | 67.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 77 | 26.0% | 29.6% | -3.6 ± 4.7 |
| chokoisky | 77 | 35.1% | 40.3% | -5.2 ± 4.9 |
| frawley | 74 | 32.4% | 30.8% | +1.6 ± 4.7 |
