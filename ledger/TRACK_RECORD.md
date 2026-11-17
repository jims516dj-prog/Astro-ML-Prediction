# Live track record

_Updated 2026-11-17T00:51:48+00:00 · 902 settled · 62 pending · 1024/1024 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 902 | 0.1944 | 0.9352 | 57.2% | — |
| engine4 | 902 | 0.1951 | 0.9373 | 56.3% | +0.00075 [-0.00006, +0.00182] |
| synthesis | 902 | 0.1944 | 0.9352 | 57.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 902 | 30.8% | 32.8% | -2.0 ± 1.4 |
| chokoisky | 902 | 34.8% | 35.8% | -0.9 ± 1.5 |
| frawley | 885 | 38.5% | 36.8% | +1.7 ± 1.5 |
