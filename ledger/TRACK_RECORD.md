# Live track record

_Updated 2026-11-27T09:07:14+00:00 · 1525 settled · 191 pending · 1802/1802 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 1525 | 0.2000 | 0.9522 | 55.5% | — |
| engine4 | 1525 | 0.2004 | 0.9535 | 55.0% | +0.00044 [-0.00003, +0.00106] |
| synthesis | 1525 | 0.2000 | 0.9522 | 55.5% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 1525 | 31.3% | 32.3% | -1.0 ± 1.1 |
| chokoisky | 1525 | 35.3% | 36.5% | -1.2 ± 1.1 |
| frawley | 1497 | 38.9% | 36.7% | +2.2 ± 1.1 |
