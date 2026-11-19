# Live track record

_Updated 2026-11-19T14:30:23+00:00 · 955 settled · 75 pending · 1095/1095 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 955 | 0.1933 | 0.9331 | 57.1% | — |
| engine4 | 955 | 0.1940 | 0.9351 | 56.2% | +0.00071 [-0.00005, +0.00161] |
| synthesis | 955 | 0.1933 | 0.9331 | 57.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 955 | 30.5% | 32.2% | -1.7 ± 1.4 |
| chokoisky | 955 | 35.1% | 35.8% | -0.7 ± 1.4 |
| frawley | 938 | 38.4% | 37.0% | +1.4 ± 1.4 |
