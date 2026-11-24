# Live track record

_Updated 2026-11-24T10:42:11+00:00 · 1372 settled · 111 pending · 1565/1565 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1372 | 0.2008 | 0.9556 | 55.1% | — |
| engine4 | 1372 | 0.2012 | 0.9570 | 54.5% | +0.00049 [-0.00004, +0.00123] |
| synthesis | 1372 | 0.2008 | 0.9556 | 55.1% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1372 | 30.0% | 31.7% | -1.6 ± 1.2 |
| chokoisky | 1372 | 35.0% | 36.0% | -1.0 ± 1.2 |
| frawley | 1347 | 39.6% | 37.3% | +2.3 ± 1.2 |
