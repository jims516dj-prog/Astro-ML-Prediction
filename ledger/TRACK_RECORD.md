# Live track record

_Updated 2026-11-15T17:22:28+00:00 · 843 settled · 88 pending · 980/980 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 843 | 0.1969 | 0.9444 | 56.2% | — |
| engine4 | 843 | 0.1977 | 0.9467 | 55.3% | +0.00080 [-0.00005, +0.00189] |
| synthesis | 843 | 0.1969 | 0.9444 | 56.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 843 | 31.4% | 33.2% | -1.8 ± 1.5 |
| chokoisky | 843 | 35.2% | 35.7% | -0.5 ± 1.5 |
| frawley | 827 | 38.3% | 37.0% | +1.3 ± 1.5 |
