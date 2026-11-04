# Live track record

_Updated 2026-11-04T16:32:26+00:00 · 230 settled · 15 pending · 245/245 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 230 | 0.2068 | 0.9632 | 57.4% | — |
| engine4 | 230 | 0.2097 | 0.9715 | 53.9% | +0.00293 [+0.00016, +0.00404] |
| synthesis | 230 | 0.2068 | 0.9632 | 57.4% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 230 | 37.4% | 36.3% | +1.1 ± 3.0 |
| chokoisky | 230 | 38.3% | 37.7% | +0.5 ± 3.0 |
| frawley | 223 | 40.4% | 37.4% | +3.0 ± 3.0 |
