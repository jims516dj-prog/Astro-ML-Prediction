# Live track record

_Updated 2026-11-03T07:24:02+00:00 · 206 settled · 10 pending · 216/216 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 206 | 0.2082 | 0.9656 | 58.3% | — |
| engine4 | 206 | 0.2116 | 0.9751 | 54.4% | +0.00338 [+0.00101, +0.00458] |
| synthesis | 206 | 0.2082 | 0.9656 | 58.3% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 206 | 38.8% | 37.3% | +1.6 ± 3.1 |
| chokoisky | 206 | 37.9% | 37.1% | +0.8 ± 3.2 |
| frawley | 199 | 40.2% | 37.1% | +3.1 ± 3.2 |
