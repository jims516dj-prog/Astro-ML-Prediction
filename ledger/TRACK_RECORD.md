# Live track record

_Updated 2026-11-05T04:25:46+00:00 · 238 settled · 38 pending · 285/285 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 238 | 0.2077 | 0.9664 | 56.7% | — |
| engine4 | 238 | 0.2105 | 0.9745 | 53.4% | +0.00283 [-0.00045, +0.00400] |
| synthesis | 238 | 0.2077 | 0.9664 | 56.7% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 238 | 37.4% | 35.9% | +1.5 ± 2.9 |
| chokoisky | 238 | 38.7% | 37.3% | +1.3 ± 2.9 |
| frawley | 230 | 40.4% | 37.4% | +3.0 ± 3.0 |
