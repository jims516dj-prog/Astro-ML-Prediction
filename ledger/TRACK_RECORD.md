# Live track record

_Updated 2026-11-28T00:35:39+00:00 · 1555 settled · 325 pending · 1967/1967 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1555 | 0.2000 | 0.9528 | 55.5% | — |
| engine4 | 1555 | 0.2004 | 0.9540 | 55.0% | +0.00043 [-0.00004, +0.00104] |
| synthesis | 1555 | 0.2000 | 0.9528 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1555 | 31.7% | 32.4% | -0.7 ± 1.1 |
| chokoisky | 1555 | 35.6% | 36.5% | -1.0 ± 1.1 |
| frawley | 1527 | 38.9% | 36.7% | +2.2 ± 1.1 |
