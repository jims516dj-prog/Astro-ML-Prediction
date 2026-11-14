# Live track record

_Updated 2026-11-14T14:35:33+00:00 · 32 settled · 43 pending · 75/75 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 32 | 0.1678 | 0.8496 | 71.9% | — |
| engine4 | 32 | 0.1678 | 0.8496 | 71.9% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 32 | 0.1678 | 0.8496 | 71.9% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 32 | 21.9% | 32.2% | -10.4 ± 7.0 |
| chokoisky | 32 | 28.1% | 38.6% | -10.5 ± 7.3 |
| frawley | 30 | 43.3% | 37.4% | +6.0 ± 7.3 |
