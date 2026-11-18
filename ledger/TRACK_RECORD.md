# Live track record

_Updated 2026-11-18T07:05:58+00:00 · 947 settled · 31 pending · 1042/1042 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 947 | 0.1938 | 0.9341 | 57.0% | — |
| engine4 | 947 | 0.1945 | 0.9362 | 56.2% | +0.00071 [-0.00005, +0.00176] |
| synthesis | 947 | 0.1938 | 0.9341 | 57.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 947 | 30.5% | 32.3% | -1.7 ± 1.4 |
| chokoisky | 947 | 35.0% | 35.7% | -0.7 ± 1.4 |
| frawley | 930 | 38.2% | 36.9% | +1.3 ± 1.4 |
