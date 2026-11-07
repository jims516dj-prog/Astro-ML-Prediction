# Live track record

_Updated 2026-11-07T07:44:14+00:00 · 311 settled · 235 pending · 555/555 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 311 | 0.2086 | 0.9684 | 56.3% | — |
| engine4 | 311 | 0.2107 | 0.9746 | 53.7% | +0.00217 [-0.00011, +0.00338] |
| synthesis | 311 | 0.2086 | 0.9684 | 56.3% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 311 | 35.7% | 33.8% | +1.9 ± 2.5 |
| chokoisky | 311 | 35.0% | 35.9% | -0.9 ± 2.6 |
| frawley | 302 | 42.7% | 38.4% | +4.3 ± 2.6 |
