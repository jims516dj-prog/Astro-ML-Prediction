# Live track record

_Updated 2026-11-16T06:14:55+00:00 · 869 settled · 80 pending · 1000/1000 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 869 | 0.1964 | 0.9448 | 56.3% | — |
| engine4 | 869 | 0.1972 | 0.9470 | 55.4% | +0.00078 [-0.00005, +0.00186] |
| synthesis | 869 | 0.1964 | 0.9448 | 56.3% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 869 | 31.3% | 33.1% | -1.8 ± 1.5 |
| chokoisky | 869 | 35.0% | 35.7% | -0.7 ± 1.5 |
| frawley | 853 | 38.6% | 36.9% | +1.6 ± 1.5 |
