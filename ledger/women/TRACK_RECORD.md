# Live track record

_Updated 2026-11-28T14:21:01+00:00 · 103 settled · 4 pending · 117/117 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 103 | 0.1681 | 0.8635 | 65.0% | — |
| engine4 | 103 | 0.1686 | 0.8649 | 65.0% | +0.00051 [-0.00000, +0.00237] |
| synthesis | 103 | 0.1681 | 0.8635 | 65.0% | +0.00000 [-0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 103 | 28.2% | 29.8% | -1.6 ± 4.0 |
| chokoisky | 103 | 34.0% | 40.4% | -6.4 ± 4.1 |
| frawley | 100 | 32.0% | 34.2% | -2.2 ± 4.1 |
