# Live track record

_Updated 2026-11-12T03:59:44+00:00 · 573 settled · 69 pending · 662/662 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 573 | 0.2029 | 0.9593 | 55.5% | — |
| engine4 | 573 | 0.2041 | 0.9627 | 54.1% | +0.00118 [-0.00008, +0.00250] |
| synthesis | 573 | 0.2029 | 0.9593 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 573 | 34.7% | 34.6% | +0.2 ± 1.8 |
| chokoisky | 573 | 34.6% | 35.0% | -0.5 ± 1.9 |
| frawley | 563 | 41.2% | 38.2% | +3.0 ± 1.9 |
