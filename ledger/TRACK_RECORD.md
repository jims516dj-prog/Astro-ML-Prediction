# Live track record

_Updated 2026-11-20T23:10:39+00:00 · 1002 settled · 331 pending · 1401/1401 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1002 | 0.1974 | 0.9424 | 56.7% | — |
| engine4 | 1002 | 0.1980 | 0.9443 | 55.9% | +0.00067 [-0.00002, +0.00158] |
| synthesis | 1002 | 0.1974 | 0.9424 | 56.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1002 | 29.4% | 31.8% | -2.3 ± 1.4 |
| chokoisky | 1002 | 35.2% | 35.9% | -0.7 ± 1.4 |
| frawley | 984 | 38.5% | 36.6% | +2.0 ± 1.4 |
