# Live track record

_Updated 2026-11-03T07:47:30+00:00 · 214 settled · 15 pending · 229/229 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 214 | 0.2084 | 0.9644 | 57.9% | — |
| engine4 | 214 | 0.2115 | 0.9734 | 54.2% | +0.00315 [+0.00022, +0.00446] |
| synthesis | 214 | 0.2084 | 0.9644 | 57.9% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 214 | 38.3% | 36.9% | +1.4 ± 3.1 |
| chokoisky | 214 | 37.4% | 37.3% | +0.0 ± 3.1 |
| frawley | 207 | 41.1% | 37.2% | +3.8 ± 3.1 |
