# Live track record

_Updated 2026-11-17T23:31:28+00:00 · 939 settled · 37 pending · 1040/1040 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 939 | 0.1947 | 0.9374 | 57.0% | — |
| engine4 | 939 | 0.1954 | 0.9395 | 56.1% | +0.00072 [-0.00007, +0.00173] |
| synthesis | 939 | 0.1947 | 0.9374 | 57.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 939 | 30.7% | 32.4% | -1.7 ± 1.4 |
| chokoisky | 939 | 34.8% | 35.6% | -0.7 ± 1.4 |
| frawley | 922 | 38.1% | 36.8% | +1.3 ± 1.4 |
