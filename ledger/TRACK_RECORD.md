# Live track record

_Updated 2026-11-11T23:31:55+00:00 · 571 settled · 42 pending · 633/633 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 571 | 0.2027 | 0.9593 | 55.5% | — |
| engine4 | 571 | 0.2039 | 0.9626 | 54.1% | +0.00118 [-0.00008, +0.00250] |
| synthesis | 571 | 0.2027 | 0.9593 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 571 | 34.9% | 34.6% | +0.2 ± 1.9 |
| chokoisky | 571 | 34.5% | 35.1% | -0.6 ± 1.9 |
| frawley | 561 | 41.2% | 38.3% | +2.9 ± 1.9 |
