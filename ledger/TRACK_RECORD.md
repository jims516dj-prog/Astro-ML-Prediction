# Live track record

_Updated 2026-11-17T14:32:19+00:00 · 907 settled · 72 pending · 1040/1040 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 907 | 0.1940 | 0.9338 | 57.2% | — |
| engine4 | 907 | 0.1948 | 0.9359 | 56.3% | +0.00074 [-0.00007, +0.00178] |
| synthesis | 907 | 0.1940 | 0.9338 | 57.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 907 | 30.9% | 32.7% | -1.8 ± 1.4 |
| chokoisky | 907 | 34.8% | 35.7% | -0.8 ± 1.5 |
| frawley | 890 | 38.3% | 36.7% | +1.6 ± 1.5 |
