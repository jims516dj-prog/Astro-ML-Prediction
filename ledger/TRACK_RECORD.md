# Live track record

_Updated 2026-11-05T03:50:23+00:00 · 239 settled · 37 pending · 276/276 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 239 | 0.2074 | 0.9652 | 56.9% | — |
| engine4 | 239 | 0.2102 | 0.9732 | 53.6% | +0.00282 [-0.00044, +0.00399] |
| synthesis | 239 | 0.2074 | 0.9652 | 56.9% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 239 | 37.2% | 35.9% | +1.4 ± 2.9 |
| chokoisky | 239 | 38.9% | 37.4% | +1.5 ± 2.9 |
| frawley | 231 | 40.3% | 37.4% | +2.9 ± 3.0 |
