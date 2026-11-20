# Live track record

_Updated 2026-11-20T06:50:39+00:00 · 76 settled · 6 pending · 92/92 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 76 | 0.1583 | 0.8209 | 67.1% | — |
| engine4 | 76 | 0.1583 | 0.8209 | 67.1% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 76 | 0.1583 | 0.8209 | 67.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 76 | 26.3% | 29.7% | -3.4 ± 4.7 |
| chokoisky | 76 | 35.5% | 40.6% | -5.0 ± 4.9 |
| frawley | 73 | 32.9% | 30.9% | +1.9 ± 4.7 |
