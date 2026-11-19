# Live track record

_Updated 2026-11-19T01:07:08+00:00 · 951 settled · 66 pending · 1082/1082 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 951 | 0.1935 | 0.9336 | 57.1% | — |
| engine4 | 951 | 0.1942 | 0.9356 | 56.3% | +0.00071 [-0.00005, +0.00175] |
| synthesis | 951 | 0.1935 | 0.9336 | 57.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 951 | 30.5% | 32.2% | -1.7 ± 1.4 |
| chokoisky | 951 | 35.0% | 35.7% | -0.7 ± 1.4 |
| frawley | 934 | 38.4% | 37.0% | +1.5 ± 1.4 |
