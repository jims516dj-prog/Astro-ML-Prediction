# Live track record

_Updated 2026-11-21T05:23:28+00:00 · 1011 settled · 339 pending · 1419/1419 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1011 | 0.1971 | 0.9443 | 56.4% | — |
| engine4 | 1011 | 0.1978 | 0.9462 | 55.6% | +0.00067 [-0.00002, +0.00146] |
| synthesis | 1011 | 0.1971 | 0.9443 | 56.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1011 | 29.6% | 31.8% | -2.2 ± 1.4 |
| chokoisky | 1011 | 35.3% | 35.9% | -0.6 ± 1.4 |
| frawley | 993 | 38.4% | 36.6% | +1.8 ± 1.4 |
