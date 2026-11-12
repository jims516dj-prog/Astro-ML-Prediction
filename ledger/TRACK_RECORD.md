# Live track record

_Updated 2026-11-12T22:46:44+00:00 · 621 settled · 91 pending · 757/757 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 621 | 0.1985 | 0.9474 | 56.2% | — |
| engine4 | 621 | 0.1996 | 0.9505 | 54.9% | +0.00109 [-0.00011, +0.00238] |
| synthesis | 621 | 0.1985 | 0.9474 | 56.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 621 | 33.3% | 34.1% | -0.8 ± 1.8 |
| chokoisky | 621 | 35.6% | 35.8% | -0.2 ± 1.8 |
| frawley | 610 | 41.0% | 38.7% | +2.3 ± 1.8 |
