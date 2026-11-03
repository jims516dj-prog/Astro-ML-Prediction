# Astro Football Lab

A research instrument for sports astrology. It runs three classical methods side by side and
learns a fourth, data-derived astrological system (the **Emergent Codex**) from about 107,000 real
matches. The fourth system may speak only when it beats market odds out of sample **and** beats
charts cast for the wrong moment (placebo skies).

> For astrological research and educational purposes only. Not a betting tool. See the banner in the app.

## Install and run the app (Windows, macOS, Linux)

The trained model and results are already in the repository, so you only need to install and start the
app. Retraining is optional (see *Rebuild the research* below).

**1. Install Python 3.11.** Use 3.11: the astronomy library (pyswisseph) ships ready-made installers only
up to 3.11, so newer Pythons would need a C compiler.
- Windows: download "Python 3.11" from https://www.python.org/downloads/windows/ and tick
  **"Add python.exe to PATH"** on the first installer screen.
- macOS: download "Python 3.11" from https://www.python.org/downloads/macos/.

**2. Get the code.** The repository is private, so sign in to GitHub first. Then either
- click **Code → Download ZIP** on the repository page and unzip it, or
- `git clone https://github.com/jims516dj-prog/Astro-ML-Prediction.git` (asks you to sign in).

**3. Open a terminal in the project folder.** On Windows, open the unzipped folder in File Explorer,
click the address bar, type `cmd` and press Enter. On macOS, open Terminal, type `cd ` and drag the folder in.

**4. Install, one time (2–5 minutes):**

| Windows (Command Prompt) | macOS / Linux |
|---|---|
| `py -3.11 -m venv .venv` | `python3.11 -m venv .venv` |
| `.venv\Scripts\pip install -r requirements.txt` | `.venv/bin/pip install -r requirements.txt` |
| `.venv\Scripts\python scripts\fetch_data.py --live` | `.venv/bin/python scripts/fetch_data.py --live` |

**5. Start the app, every time:**

| Windows | macOS / Linux |
|---|---|
| `.venv\Scripts\python -m uvicorn astrofoot.web.app:app` | `.venv/bin/python -m uvicorn astrofoot.web.app:app` |

Open **http://localhost:8000**. Leave the terminal window open while you use the app, and press Ctrl+C to stop it.

**Troubleshooting**
- *"py is not recognized"* or *"python3.11: command not found"*: Python 3.11 isn't installed, or wasn't added to PATH. Re-run the installer.
- *pip tries to compile pyswisseph / "Microsoft Visual C++ required"*: the venv uses a Python newer than 3.11.
  Delete the `.venv` folder and repeat step 4 with 3.11.
- *Port 8000 already in use*: add `--port 8001` and open http://localhost:8001.
- *Venue lookup finds nothing*: type the latitude and longitude yourself (any map site shows them).

## Team founding charts (auto-filled)

Typing a team name on **Analyze** fills in its founding chart for Rao's Nations' Charts step, from
`data/ref/team_foundings.csv`: about 33,000 founding records for football clubs and the nations national
teams represent, from **Wikidata** (open data, CC0). Where Wikidata has only the year, exact dates are taken
from the club's English Wikipedia infobox when the year agrees (about 6,300 records have exact dates).
Short names work ("Man United", "Ath Madrid", "Paris SG"). When a name is ambiguous ("Wolves": Wolverhampton
or Wolfsburg), nothing is filled in and you pick from the list; well-known clubs are listed first.
Every field stays editable, other candidates (e.g. *nation* vs *national team* charts) are in the
**Chart** dropdown, and **Save as my default for this team** stores your version, which then takes
priority (in `data/app.sqlite3`, on your computer only).

- Founding **times** are almost never recorded. Without one, the chart is cast for local noon, Rao uses
  the founding **Moon only** (no Ascendant, no Saturn-on-8th check), and a warning appears if the Moon
  changed sign that day. Enter the time when you know it to use the full chart.
- Dates known only to the month or year are listed but not used: the Moon can't be placed.
- For nations, the place shown is the present-day capital; edit it if the state was founded elsewhere.
- The table is refreshed monthly by `.github/workflows/foundings.yml` (or `python scripts/fetch_foundings.py`
  wherever query.wikidata.org is reachable). Pull to get it: `git pull`.
- Live forecasts are unaffected: they never include founding charts, so the record's method stays fixed.

## Rebuild the research (optional, hours)

```sh
python scripts/fetch_data.py                      # ~65 MB of public source data -> data/raw
python scripts/research.py prepare                # dataset, real sky, classical engines   (~2 min)
python scripts/research.py evaluate               # walk-forward, controls, Tribunal, structures (~25 min)
python scripts/research.py placebo --k 10         # 30 placebo skies, identical pipeline (~1.5 h)
python scripts/research.py codex                  # final fit, Codex, one-shot vault, gate, model artifact
```

(Use the venv's python, as in step 5.) Tests: `python -m pytest tests` (fast unit tests) and
`python scripts/ml_selftest.py both` (planted-signal recovery and null test on the real lattice, ~10 min).

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

## Update now (on-demand forecasts and results)

The **Update now** button on the Live record page asks GitHub to run the forecast/results cycle immediately,
waits for it (2–3 minutes) and downloads the outcome, instead of waiting for the scheduled runs. GitHub
stays the only writer of the ledger; the button just starts the same job.

One-time setup: a token that can do only this.

1. On GitHub: your photo → **Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**.
2. Name it e.g. *astro update now*, pick an expiry (e.g. 90 days). **Repository access: Only select
   repositories → Astro-ML-Prediction**. **Permissions → Repository permissions → Actions: Read and write**
   (nothing else). Generate, and copy the token (it starts with `github_pat_`).
3. In the project folder create a file named `.github_token` containing just that token, e.g. in Git Bash:
   `cat > .github_token`, paste, press Enter, then Ctrl+D. The file is git-ignored and never uploaded.
   (Alternatively set the environment variable `GITHUB_TOKEN`.)
4. Restart the app.

To revoke it, delete the token on GitHub (same page) or delete the file. When the token expires, Update now
says so ("your GitHub token has expired or was revoked…") and still downloads whatever GitHub has already
published; generate a new token (steps 1–2) and replace the contents of `.github_token`.

## Faster results (second source, optional)

football-data.co.uk sometimes publishes results a day or more late. For the top leagues the cycle can also
ask **football-data.org** (official API, free plan), which has scores minutes after full time.

Covered: Premier League, Championship, Bundesliga, Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga,
Brasileirão.

Every other league (and any top-league game football-data.org misses) is looked up on **ESPN's public
scoreboard feed**, which needs no key. It is unofficial: if it changes or goes down, those games simply
wait for football-data.co.uk. Games decided after extra time or penalties are left to football-data.co.uk.

One-time setup:

1. Register at <https://www.football-data.org/client/register> (free). The API key arrives by email.
2. On GitHub: the repository → **Settings → Secrets and variables → Actions → New repository secret**.
   Name: `FOOTBALL_DATA_ORG_TOKEN`, value: the key. (Never paste it into a chat or a committed file.)
3. Done. The next cycle (scheduled, or Update now) uses it; the run log shows
   `football-data.org: N of M pending top-league result(s) found`.

How it is kept honest:

- A match is paired only when league, kickoff (±3 h) and both team names agree; any doubt leaves it pending.
- Scores are after 90 minutes (plus stoppage time), like the primary source; extra time and penalties are ignored.
- Every result records its source. When football-data.co.uk later publishes the same match, the ledger
  appends a *confirms* record, or a *corrects* record if the scores differ (the primary source wins).
- For running it on your own computer, set the environment variable `FOOTBALL_DATA_ORG_TOKEN` instead.

## The living Engine 4

Engine 4 is retrained every week by `.github/workflows/retrain.yml` (`python scripts/research.py living`):

1. **Data grows daily.** The training table is the historical corpus plus every live match that has
   settled since the previous run (forecast sealed before kickoff, result in).
2. **Inputs:** 2,463 sky primitives (all zodiacs, house systems, aspects, angles, lordships, Moon, time
   lords) **plus the three books**: every Rao, Chokoisky and Frawley testimony type as a signed feature
   (+ for the favourite), and each engine's verdict and net score. Engine 4 can learn which classical
   patterns, alone or alongside sky configurations, carry signal, and how much.
3. **Baseline:** de-vigged odds plus calendar/scheduling controls. Elo and form are not used: live
   fixtures don't have them. Astrology is only credited with what it adds beyond this baseline.
4. **Learning:** sparse (L1) model on the residual, penalty chosen by inner validation with the
   one-standard-error rule, walk-forward over every season since 2020/21.
5. **Publishing:** each run publishes `engine4_vN`. Live forecasts use the newest version, and the
   ledger records which version made each forecast; the Live record page scores every version
   separately against the market.
6. **When nothing has been learned**, Engine 4 outputs the de-vigged odds themselves.
7. **The gate** decides whether Engine 4 also drives the headline synthesis: its walk-forward ΔRPS must
   beat the baseline with a 95% CI excluding zero **and** the real sky must beat ≥ 95% of placebo skies
   (refreshed monthly by `.github/workflows/placebo.yml`, with Engines 1-3 re-run on the placebo charts).
   The one-shot vault (2025/26) was spent on the first version, so its seasons are now training data and
   the prospective live record is the out-of-sample test.

## Live track record

The backtest can only show that nothing *was* predictable. A live record shows whether anything *is*:
forecasts for real upcoming matches, committed before kickoff and scored afterwards.

```sh
python scripts/fetch_data.py --live  # venue tables only, if data/raw is missing
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
