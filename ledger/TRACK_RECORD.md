# Live track record

_Updated 2026-11-22T13:27:39+00:00 · 1207 settled · 177 pending · 1457/1457 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1207 | 0.2008 | 0.9564 | 55.0% | — |
| engine4 | 1207 | 0.2013 | 0.9580 | 54.3% | +0.00056 [-0.00004, +0.00141] |
| synthesis | 1207 | 0.2008 | 0.9564 | 55.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1207 | 29.2% | 30.9% | -1.7 ± 1.2 |
| chokoisky | 1207 | 34.8% | 35.8% | -1.0 ± 1.3 |
| frawley | 1185 | 39.2% | 36.8% | +2.4 ± 1.3 |
