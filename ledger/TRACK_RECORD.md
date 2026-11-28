# Live track record

_Updated 2026-11-28T14:20:00+00:00 · 1580 settled · 334 pending · 2001/2001 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1580 | 0.2002 | 0.9526 | 55.5% | — |
| engine4 | 1580 | 0.2006 | 0.9535 | 55.0% | +0.00039 [-0.00008, +0.00101] |
| synthesis | 1580 | 0.2002 | 0.9526 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1580 | 31.6% | 32.3% | -0.7 ± 1.1 |
| chokoisky | 1580 | 35.8% | 36.5% | -0.8 ± 1.1 |
| frawley | 1552 | 38.9% | 36.7% | +2.2 ± 1.1 |
