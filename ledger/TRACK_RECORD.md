# Live track record

_Updated 2026-11-14T06:28:34+00:00 · 715 settled · 173 pending · 935/935 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 715 | 0.1985 | 0.9511 | 55.8% | — |
| engine4 | 715 | 0.1995 | 0.9538 | 54.7% | +0.00094 [+0.00002, +0.00211] |
| synthesis | 715 | 0.1985 | 0.9511 | 55.8% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 715 | 32.0% | 33.6% | -1.6 ± 1.6 |
| chokoisky | 715 | 36.1% | 36.3% | -0.3 ± 1.6 |
| frawley | 701 | 39.8% | 38.5% | +1.3 ± 1.7 |
