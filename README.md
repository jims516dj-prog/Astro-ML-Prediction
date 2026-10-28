# Astro Football Lab

A research instrument for sports astrology. It runs three classical methods side by side and
learns a fourth, data-derived astrological system (the **Emergent Codex**) from about 107,000 real
matches. The fourth system may speak only when it beats market odds out of sample **and** beats
charts cast for the wrong moment (placebo skies).

> For astrological research and educational purposes only. Not a betting tool. See the banner in the app.

## Quick start

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./fetch_data.sh                                   # ~65 MB of public source data -> data/raw
.venv/bin/python scripts/research.py prepare      # dataset, real sky, classical engines   (~2 min)
.venv/bin/python scripts/research.py evaluate     # walk-forward, controls, Tribunal, structures (~25 min)
.venv/bin/python scripts/research.py placebo --k 10   # 30 placebo skies, identical pipeline (~1.5 h)
.venv/bin/python scripts/research.py codex        # final fit, Codex, one-shot vault, gate, model artifact
.venv/bin/uvicorn astrofoot.web.app:app --port 8000
```

Then open http://localhost:8000.

Tests: `.venv/bin/python -m pytest tests` (fast unit tests) and
`.venv/bin/python scripts/ml_selftest.py both` (planted-signal recovery and null test on the real lattice, ~10 min).

## What is in the box

| Layer | Module | Notes |
|---|---|---|
| Ephemeris | `astrofoot/ephem.py` | Swiss Ephemeris (Moshier, no data files). Tropical, Lahiri, KP. Placidus / Regiomontanus / Campanus / Equal / Whole Sign. D9, antiscia, KP sublords, planetary hours, eclipses. Porphyry fallback in the polar circle. |
| Engine 1 | `engines/rao.py` | Rao: Lahiri, whole-sign, favourite as Lagna. The 0–3 judgement is an explicit, documented algorithm. Nations' Charts and the captain/jersey layer run only when their inputs are supplied. |
| Engine 2 | `engines/chokoisky.py` | Chokoisky: victory houses, SKY/PKY, D1 and D9 cuspal strength, nama pada (108 syllables), KP sublords and sublord array, yogataras, planetary war. |
| Engine 3 | `engines/frawley.py` | Frawley: tropical Placidus, Lords 1/10 v 7/4, on-cusp v just-inside, antiscia, Moon placement, Fortuna antiscion, Moon's last aspect (5° window), Fortuna aspects, dispositor, nodes/combustion/Pluto/Saturn/Uranus, default rule. |
| Data | `dataset.py`, `geo.py` | football-data.co.uk (via xgabora) with UK-clock kickoff times converted to UTC, de-vigged odds, favourite/home frames. Venues come from stadium GPS (17k matches), hand-curated club→city (42k) and city matching (47k). |
| Lattice | `lattice.py`, `sky.py` | 2,531 interpretable primitives in four blocks (sky state, zodiac placements, angles, houses/lordship) across 2 zodiacs × 5 house systems. Real and placebo skies. |
| Learning | `models.py`, `pipeline.py` | M0 = market + controls (league, season, month, weekday, kickoff hour, Elo, form). Engine 4 = L1 offset-softmax on the residual. Frame and λ are chosen inside each fold. Seasonal walk-forward 2020/21–2024/25; 2025/26 onward is the vault. |
| Evidence | `codex.py`, `scripts/research.py` | Doctrine Tribunal (74 classical doctrines, Holm), structural comparisons, coin-frame negative control, placebo skies, stability selection, BH-FDR, out-of-time replication, league consistency, learned-orb curves, gate. |
| App | `web/` | Analyze (incl. venue lookup, captains/jerseys, founding charts), match record (4 engines + market + synthesis, chart wheels, result entry, edit with audit and re-run versions, SHA-256 ledger), dataset browser and export, Codex, ML dashboard. |

## Decisions that differ from the spec, and why

- **One Python app instead of Next.js + Postgres + a FastAPI microservice.** The astronomy and ML are Python.
  A single process is easier to reproduce and run, and SQLite plus Parquet hold everything the app needs.
- **The market is the baseline.** Every learned model fits the residual over de-vigged odds plus calendar
  and scheduling controls. "Accuracy versus a coin flip" is never used as evidence.
- **Confidence is a calibrated probability.** The heuristic consensus score is shown, but labelled as not a probability.
- **The gate.** Engine 4 gets zero weight until its walk-forward ΔRPS CI excludes zero *and* the real sky beats ≥95% of placebo skies.
- **Not implemented:** the goal-timing study (§12.9). It needs minute-level goal events with exact
  kickoff times and stadium coordinates for thousands of matches. The open event data available here
  has too few such matches with reliable kickoff times, so it was deferred rather than faked. Upaketu,
  Gulika, Ceres, Chiron and stolen-cusp adjustments are also not implemented; each engine's caveats
  list says so on every analysis.
- **Tables to verify against the books** (marked `VERIFY` in `tables.py`): Rao's node friendships and the
  108-syllable table (standard Avakahada chakra is used).

## Live track record

The backtest can only show that nothing *was* predictable. A live record shows whether anything *is*:
forecasts for real upcoming matches, committed before kickoff and scored afterwards.

```sh
./fetch_data.sh live                 # venue tables only, if data/raw is missing
python scripts/live.py cycle         # settle finished matches, forecast the next 4 days, rebuild the report
git add ledger && git commit -m "ledger" && git push     # before the earliest kickoff
python scripts/live.py verify        # re-check every record's SHA-256
```

- Source: football-data.co.uk `fixtures.csv` (Bet365 odds first, the same bookmaker as the training data)
  and its season results files. The host must be reachable from wherever this runs.
- `ledger/predictions/*.jsonl` and `ledger/results.jsonl` are append-only. Each record is sealed with a
  SHA-256 of its contents, and anything committed after kickoff is excluded from scoring.
- `ledger/TRACK_RECORD.md` scores Engine 4 and the synthesis against the market (RPS, log loss, CI once n ≥ 30),
  and each classical engine's hit rate against what the odds implied for the same picks.
- `.github/workflows/track-record.yml` runs the cycle twice a day and pushes the ledger. GitHub schedules
  workflows only on a repository's default branch, so it activates once the project has its own repo.
- The app's **Live record** page shows the same ledger (`ASTRO_LEDGER=path` points it elsewhere).

## Findings (lattice L-2026.1, model v1)

- **No astrological edge.** Across 58,568 out-of-sample matches, Engine 4 did not improve on the market-based
  control model (ΔRPS +0.000001, 95% CI −0.000001 to +0.000004). Inner validation chose the null model in 4 of 5
  folds. The real sky ranked better than only 76% of 21 placebo skies; the gate requires 95%.
- **The three books on trial:** all 74 classical doctrines are *not supported* against market odds
  (Chokoisky 38, Frawley 30, Rao 6). Re-weighting the three engines (M1) is slightly worse than the market.
- **No zodiac or house-system preference** is demonstrated: tropical, Lahiri and five house systems all fail to beat the market.
- **Vault** (8,288 matches from 2025/26, evaluated once): ΔRPS 0.
- **The pipeline can find real effects.** A planted +6.7 pp effect on a configuration present in ~9% of matches
  is recovered as the only primitive and validated out of sample. A planted +3.4 pp effect is recovered but
  not validated. Pure-noise data yields nothing. The null therefore rules out effects of roughly this size or
  larger for common configurations; it cannot rule out smaller effects or effects of rare configurations.
- **Bugs the controls caught** (all fixed, with regression tests): single-season inner validation hid
  calendar-clustered effects; a slow-planet aspect absent from training exploded predictions on one placebo
  sky; a polar-latitude sunrise edge case.

Full tables: `FINDINGS.md`, which is regenerated from `data/models/*.json` after each training run, or the
Codex and ML pages in the app.

## Data sources and licences

- Match results and odds: football-data.co.uk, via `xgabora/Club-Football-Match-Data-2000-2025`.
- Stadium coordinates: `jokecamp/FootballData`.
- Cities: `dr5hn/countries-states-cities-database` (ODbL, attribution required).
- Swiss Ephemeris: AGPL/commercial dual licence (pyswisseph).
