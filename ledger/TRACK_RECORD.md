# Live track record

_Updated 2026-11-04T22:40:08+00:00 · 235 settled · 10 pending · 245/245 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 235 | 0.2081 | 0.9673 | 57.0% | — |
| engine4 | 235 | 0.2110 | 0.9755 | 53.6% | +0.00287 [+0.00016, +0.00400] |
| synthesis | 235 | 0.2081 | 0.9673 | 57.0% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 235 | 37.4% | 36.1% | +1.3 ± 2.9 |
| chokoisky | 235 | 38.7% | 37.6% | +1.2 ± 3.0 |
| frawley | 227 | 40.5% | 37.2% | +3.3 ± 3.0 |
