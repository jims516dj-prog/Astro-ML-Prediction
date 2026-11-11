# Live track record

_Updated 2026-11-11T12:48:39+00:00 · 568 settled · 42 pending · 630/630 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 568 | 0.2025 | 0.9597 | 55.5% | — |
| engine4 | 568 | 0.2037 | 0.9631 | 54.0% | +0.00119 [-0.00008, +0.00250] |
| synthesis | 568 | 0.2025 | 0.9597 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 568 | 34.9% | 34.7% | +0.1 ± 1.9 |
| chokoisky | 568 | 34.3% | 34.9% | -0.6 ± 1.9 |
| frawley | 558 | 41.2% | 38.4% | +2.8 ± 1.9 |
