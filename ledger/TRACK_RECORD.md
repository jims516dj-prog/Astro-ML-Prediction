# Live track record

_Updated 2026-11-27T19:59:17+00:00 · 1535 settled · 326 pending · 1948/1948 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1535 | 0.1998 | 0.9508 | 55.7% | — |
| engine4 | 1535 | 0.2003 | 0.9521 | 55.2% | +0.00044 [-0.00003, +0.00106] |
| synthesis | 1535 | 0.1998 | 0.9508 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1535 | 31.5% | 32.3% | -0.9 ± 1.1 |
| chokoisky | 1535 | 35.4% | 36.5% | -1.1 ± 1.1 |
| frawley | 1507 | 39.0% | 36.7% | +2.2 ± 1.1 |
