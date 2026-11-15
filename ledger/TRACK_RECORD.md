# Live track record

_Updated 2026-11-15T23:30:39+00:00 · 859 settled · 70 pending · 980/980 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 859 | 0.1964 | 0.9436 | 56.2% | — |
| engine4 | 859 | 0.1971 | 0.9459 | 55.3% | +0.00078 [-0.00005, +0.00189] |
| synthesis | 859 | 0.1964 | 0.9436 | 56.2% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 859 | 31.4% | 33.2% | -1.8 ± 1.5 |
| chokoisky | 859 | 35.0% | 35.7% | -0.7 ± 1.5 |
| frawley | 843 | 38.2% | 36.9% | +1.3 ± 1.5 |
