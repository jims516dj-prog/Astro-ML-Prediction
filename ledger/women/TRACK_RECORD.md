# Live track record

_Updated 2026-11-28T00:35:48+00:00 · 99 settled · 4 pending · 113/113 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 99 | 0.1716 | 0.8820 | 63.6% | — |
| engine4 | 99 | 0.1716 | 0.8820 | 63.6% | +0.00000 [-0.00000, +0.00000] |
| synthesis | 99 | 0.1716 | 0.8820 | 63.6% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 99 | 28.3% | 29.4% | -1.2 ± 4.1 |
| chokoisky | 99 | 34.3% | 40.5% | -6.2 ± 4.2 |
| frawley | 96 | 31.2% | 34.1% | -2.9 ± 4.1 |
