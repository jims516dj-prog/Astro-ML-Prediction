# Live track record

_Updated 2026-11-20T01:01:28+00:00 · 960 settled · 224 pending · 1250/1250 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 960 | 0.1935 | 0.9335 | 57.1% | — |
| engine4 | 960 | 0.1942 | 0.9355 | 56.2% | +0.00070 [-0.00005, +0.00160] |
| synthesis | 960 | 0.1935 | 0.9335 | 57.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 960 | 30.4% | 32.1% | -1.7 ± 1.4 |
| chokoisky | 960 | 35.0% | 35.7% | -0.7 ± 1.4 |
| frawley | 942 | 38.4% | 36.9% | +1.5 ± 1.4 |
