# Live track record

_Updated 2026-11-16T13:44:52+00:00 · 879 settled · 82 pending · 1018/1018 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 879 | 0.1970 | 0.9445 | 56.4% | — |
| engine4 | 879 | 0.1977 | 0.9467 | 55.5% | +0.00077 [-0.00005, +0.00186] |
| synthesis | 879 | 0.1970 | 0.9445 | 56.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 879 | 30.9% | 33.0% | -2.1 ± 1.5 |
| chokoisky | 879 | 34.8% | 35.7% | -0.8 ± 1.5 |
| frawley | 862 | 38.5% | 36.8% | +1.7 ± 1.5 |
