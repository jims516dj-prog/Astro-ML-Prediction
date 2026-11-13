# Live track record

_Updated 2026-11-13T17:42:26+00:00 · 653 settled · 190 pending · 888/888 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 653 | 0.1983 | 0.9548 | 55.4% | — |
| engine4 | 653 | 0.1994 | 0.9577 | 54.2% | +0.00103 [-0.00008, +0.00234] |
| synthesis | 653 | 0.1983 | 0.9548 | 55.4% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 653 | 33.4% | 34.2% | -0.8 ± 1.7 |
| chokoisky | 653 | 36.0% | 35.7% | +0.2 ± 1.7 |
| frawley | 642 | 40.2% | 38.9% | +1.3 ± 1.8 |
