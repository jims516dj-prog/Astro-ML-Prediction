# Live track record

_Updated 2026-11-25T15:42:39+00:00 · 1442 settled · 92 pending · 1619/1619 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1442 | 0.2007 | 0.9565 | 54.9% | — |
| engine4 | 1442 | 0.2012 | 0.9578 | 54.4% | +0.00047 [-0.00004, +0.00115] |
| synthesis | 1442 | 0.2007 | 0.9565 | 54.9% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1442 | 30.8% | 31.9% | -1.1 ± 1.1 |
| chokoisky | 1442 | 35.0% | 36.4% | -1.3 ± 1.2 |
| frawley | 1417 | 39.1% | 36.9% | +2.2 ± 1.2 |
