# Live track record

_Updated 2026-11-15T21:52:21+00:00 · 855 settled · 74 pending · 980/980 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 855 | 0.1964 | 0.9436 | 56.3% | — |
| engine4 | 855 | 0.1972 | 0.9459 | 55.3% | +0.00079 [-0.00005, +0.00189] |
| synthesis | 855 | 0.1964 | 0.9436 | 56.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 855 | 31.3% | 33.1% | -1.8 ± 1.5 |
| chokoisky | 855 | 35.2% | 35.7% | -0.5 ± 1.5 |
| frawley | 839 | 38.1% | 36.9% | +1.2 ± 1.5 |
