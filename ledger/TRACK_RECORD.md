# Live track record

_Updated 2026-11-07T11:48:55+00:00 · 314 settled · 236 pending · 559/559 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 314 | 0.2082 | 0.9681 | 56.4% | — |
| engine4 | 314 | 0.2103 | 0.9742 | 53.8% | +0.00215 [-0.00010, +0.00335] |
| synthesis | 314 | 0.2082 | 0.9681 | 56.4% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 314 | 35.7% | 33.9% | +1.8 ± 2.5 |
| chokoisky | 314 | 35.0% | 35.8% | -0.8 ± 2.5 |
| frawley | 305 | 42.6% | 38.4% | +4.2 ± 2.6 |
