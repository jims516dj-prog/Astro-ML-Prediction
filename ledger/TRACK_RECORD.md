# Live track record

_Updated 2026-11-09T00:28:29+00:00 · 502 settled · 58 pending · 569/569 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 502 | 0.2005 | 0.9496 | 56.6% | — |
| engine4 | 502 | 0.2018 | 0.9534 | 55.0% | +0.00134 [+0.00001, +0.00282] |
| synthesis | 502 | 0.2005 | 0.9496 | 56.6% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 502 | 34.9% | 34.9% | -0.0 ± 2.0 |
| chokoisky | 502 | 33.9% | 34.8% | -1.0 ± 2.0 |
| frawley | 492 | 41.1% | 38.5% | +2.6 ± 2.0 |
