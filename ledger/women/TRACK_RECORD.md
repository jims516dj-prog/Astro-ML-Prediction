# Live track record

_Updated 2026-11-27T14:50:10+00:00 · 97 settled · 6 pending · 113/113 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 97 | 0.1741 | 0.8946 | 62.9% | — |
| engine4 | 97 | 0.1741 | 0.8946 | 62.9% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 97 | 0.1741 | 0.8946 | 62.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 97 | 28.9% | 29.9% | -1.0 ± 4.1 |
| chokoisky | 97 | 34.0% | 40.2% | -6.2 ± 4.3 |
| frawley | 94 | 29.8% | 33.1% | -3.4 ± 4.2 |
