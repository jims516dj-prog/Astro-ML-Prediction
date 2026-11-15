# Live track record

_Updated 2026-11-15T23:30:55+00:00 · 67 settled · 6 pending · 79/79 records verify · 0 excluded as committed after kickoff_

Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record carries a SHA-256 of its contents. Only these pre-registered forecasts count.

## Probabilistic forecasts (lower RPS / log loss is better)

| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |
|---|---|---|---|---|---|
| market | 67 | 0.1711 | 0.8816 | 62.7% | — |
| engine4 | 67 | 0.1711 | 0.8816 | 62.7% | +0.00000 [+0.00000, +0.00000] |
| synthesis | 67 | 0.1711 | 0.8816 | 62.7% | +0.00000 [+0.00000, +0.00000] |

## Classical verdicts (hit rate vs what the odds implied for the same picks)

| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |
|---|---|---|---|---|
| rao | 67 | 29.9% | 31.8% | -1.9 ± 5.1 |
| chokoisky | 67 | 28.4% | 37.8% | -9.5 ± 5.2 |
| frawley | 64 | 32.8% | 30.4% | +2.4 ± 5.0 |
