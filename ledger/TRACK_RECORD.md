# Live track record

_Updated 2026-11-13T10:52:31+00:00 · 635 settled · 185 pending · 865/865 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 635 | 0.1982 | 0.9509 | 55.7% | — |
| engine4 | 635 | 0.1993 | 0.9539 | 54.5% | +0.00106 [-0.00008, +0.00241] |
| synthesis | 635 | 0.1982 | 0.9509 | 55.7% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 635 | 33.2% | 34.2% | -0.9 ± 1.7 |
| chokoisky | 635 | 35.7% | 35.8% | -0.0 ± 1.8 |
| frawley | 624 | 40.4% | 38.5% | +1.9 ± 1.8 |
