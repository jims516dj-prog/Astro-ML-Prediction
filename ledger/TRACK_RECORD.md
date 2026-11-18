# Live track record

_Updated 2026-11-18T23:29:02+00:00 · 950 settled · 28 pending · 1042/1042 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 950 | 0.1935 | 0.9337 | 57.1% | — |
| engine4 | 950 | 0.1942 | 0.9358 | 56.2% | +0.00071 [-0.00005, +0.00175] |
| synthesis | 950 | 0.1935 | 0.9337 | 57.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 950 | 30.5% | 32.2% | -1.7 ± 1.4 |
| chokoisky | 950 | 35.1% | 35.7% | -0.7 ± 1.4 |
| frawley | 933 | 38.4% | 36.9% | +1.4 ± 1.4 |
