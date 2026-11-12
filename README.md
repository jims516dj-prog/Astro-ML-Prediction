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

## More fixtures and odds (optional)

football-data.co.uk refreshes its fixtures list about twice a week (typically Tuesday and Friday), so games
announced in between had no forecast. **The Odds API** (free plan, 500 credits a month) fills those gaps.

One-time setup:

1. Register at <https://the-odds-api.com> (choose the free plan). The API key arrives by email.
2. On GitHub: the repository → **Settings → Secrets and variables → Actions → New repository secret**.
   Name: `ODDS_API_KEY`, value: the key.
3. The next cycle logs `the-odds-api.com: N extra fixture(s); odds bought for …; X credits left this month`.

How it works:

- Listing a league's upcoming games is free. Odds cost 1 credit per league request, and are bought only when
  that league has a game in the next 30 hours that football-data.co.uk does not list and that has no forecast
  yet, at most once every 20 hours per league, and never below 25 credits left. Normal use stays within
  the free 500 a month.
- Team names are translated to football-data.co.uk's spelling (from the league's current-season results), so
  the venue resolves and the forecast's match key is the same one the primary uses for the fixture and the
  result. A name that cannot be paired confidently skips that game (listed in the run log).
- Odds: Bet365 if offered (the bookmaker the model was trained on), otherwise the average across
  bookmakers, like football-data.co.uk's "Avg" columns. Each forecast records which in `odds_source`.
  These forecasts have no over/under 2.5 price, so that one input is left out.
- National League and Scottish tiers below the Premiership are not covered; they still rely on football-data.co.uk.

## Top picks: over/under 2.5 goals

The Over/under 2.5 tab ranks the day's matches by the probability of the likelier side of 2.5 goals, and shows each classical engine's
predicted total, how many agree, and the result.

- **Probability:** the market's over/under price, recalibrated (`p' = σ(a + b·logit p)`, b ≈ 1.12) because
  proportional de-vigging understates the likelier side. Fitted walk-forward on 53,078 historical matches:
  the top-10/day rule hit 62.1% vs 61.9% expected out of sample. Without recalibration it would have
  claimed 60.8%, an apparent edge that was only the bookmaker's margin.
- **Astrology:** Rao's and Chokoisky's predicted scores are fixed functions of their net points, so their
  over/under calls were rebuilt for every historical match. Neither beats the market: Rao −0.4 points,
  Chokoisky +0.3 points (both within ±2 SE). Agreement with the pick adds nothing. Frawley's goal count needs
  testimony counts the history does not store, so it is shown live only.
- `python scripts/research.py overunder` rebuilds `data/models/overunder.json` (2 seconds); the weekly
  retrain refreshes it automatically.
- Forecasts without an over/under price (some extra leagues, games from The Odds API) are not ranked.

## Top picks: home or away goal

The third tab ranks up to 10 matches a day by the team likelier to **score at least once**, home or away.

- **Probability:** the market does not price "team to score" in our data, so it is derived from the de-vigged
  1X2 odds: the Poisson scoring rates that reproduce the home-win and away-win probabilities give
  P(team scores) = 1 − e^(−λ). That raw model understates scoring (home teams score 76.4% of the time; it
  says 72.5%), so it is recalibrated walk-forward. Out of sample, every probability band is within about a
  point of the observed rate, and the top-10/day rule scored 85.2% vs 85.3% expected over 29,468 picks (74.5%
  of them home teams). The over/under price added nothing, so every forecast can be ranked.
- **Astrology:** each engine's predicted score says whether each team scores. Rao: −0.2 points vs the market
  (slightly below); Chokoisky: −0.0. Both engines' rarer "fails to score" calls are about +2 SE, which, with
  four comparisons, is a hypothesis for the live record, not an edge. Frawley: live only.
- Rebuilt with the over/under step: `python scripts/research.py overunder` (writes `data/models/teamgoals.json`).

## Home or away goal: quick guide

The **Home or away goal** tab opens with a *Quick guide* panel (collapsible) of plain-odds rules for whether the home or
away team scores, computed from the historical corpus (`research.py overunder` → `data/models/scoring_guide.json`,
refreshed weekly): (1) how often a team scored by its **win odds** (home and away alike: under 1.70 ≈ 85%+, 4.00+ close
to a coin flip); (2) the **over/under 2.5** price as a tie-breaker (home under 1.70 with over 2.5 under 1.80: 92%; away
under 2.50: 87%); (3) **expected goals** (1.5+: 87%, 2.0+: 92%, under 0.8: 55%) and the quickest app routes; (4) the
leagues where away teams score least or most, and what not to rely on (engine agreement, form windows).

## Top picks: both teams to score, and goal predictions everywhere

The fourth tab ranks up to 10 matches a day by whether **both teams score** (yes or no) is most probable. It uses
the same Poisson scoring rates as "home or away goal", recalibrated on a rolling window of the three previous
seasons, because the both-score rate drifts (50.5% in 2014/15, about 55% now). It is the hardest of the four
markets: the top-10/day rule was right 57.7% of the time vs 58.1% expected (29,468 picks), and the model only just
beats always saying the average rate (log loss 0.686 vs 0.692). Rao and Chokoisky: within noise.

**Every game now gets all three goal predictions** (over/under 2.5, home or away goal, both teams to score), with
✓/✗ once the score is in:

- **Analyze** (new games): an optional *Over 2.5 / Under 2.5* odds pair on the form gives the over/under
  prediction; the other two come from the match odds. Each analysis shows a *Goals* card with probabilities,
  and each engine's predicted score with its three calls.
- **Dataset**: a *Goals* column on your matches, the completed live forecasts and all 107,462 corpus matches.
- **Live record**: a *Goals* column on every forecast; each forecast's page has the goals card.

All of them use one function (`astrofoot/goalmarkets.py`), so a game shows the same numbers everywhere.

## Top picks: every game, six markets

Top picks now ranks **every** forecast match of the day (no 10-game cap) in six tabs: Match result, **Double
chance**, **Over/under 1.5**, Over/under 2.5, Home or away goal, Both teams to score. Filters: day, astrology
agreement, and **minimum probability** (60%+ … 90%+). Under each table, "How often picks at each probability come
true" compares live and backtest hit rates per probability band, so you can pick a threshold that holds up.

- **Double chance** (1X, X2, 12): the sum of two de-vigged 1X2 probabilities. Already calibrated without any
  correction: picks won 77.6% of the time vs 77.5% claimed over 107,462 matches. All three engines are backtested
  (their predicted winners are stored): agreeing with them adds nothing (Rao −0.0, Chokoisky +0.0, Frawley −0.0
  points).
- **Over/under 1.5**: from the total Poisson scoring rate, recalibrated on the last three seasons; 74.3% vs 74.5%
  expected. About 74% of matches have 2+ goals, so picks are almost always "over". Rao always predicts 2+
  goals; neither engine adds anything.
- The backtest tiles now score **all** picks (the rule the page applies), not just the top 10 a day.
- Every Dataset, Live and Analyze view shows all five goal-and-chance predictions as badges/cards.

## Tennis (Soccer / Tennis switch)

The **⚽ Soccer / 🎾 Tennis** switch in the header changes the whole interface. Tennis has its own pages:

- **Forecasts** (`/tennis`): every upcoming ATP and WTA singles match starting within 36 hours, with each player's
  chance to **win a given set**, **win the first set**, **win at least one set** and **win the match**. Forecasts are sealed
  (SHA-256) and committed to `ledger/tennis/` before the start by the same GitHub cycle as the soccer record (05:17,
  11:17, 17:17 UTC), then scored against ESPN's results (`ledger/tennis/TRACK_RECORD.md`).
- **Match** pages: the probabilities and every factor the model saw, in three groups.
- **Analyze**: any two players (from the history, or new ones with a date of birth), surface, format and time.
- **Dataset**: every completed singles match ESPN lists since 2010 (about 110,000). Filters: tour, surface, year, date
  range, round, best of 3/5, seeds (both, one, neither, unseeded beat a seed), level (tour, WTA 125, Challenger, ITF women /
  men, team events, all women's / men's), player, tournament, and whether the day's
  astrology / numerology favourite won, lost or was level; plus how often the day's favourites won under the other filters.
  The soccer Dataset's Men / Women switch also has Tennis.
- **ML model**: what the model learned and how well it does (below), with **Retrain** buttons.

**Data.** ESPN's public tennis feed (no key): matches with set-by-set scores, seeds and qualifier/wildcard tags, and
each player's date and place of birth. ESPN does not publish surfaces, so they are inferred from the tournament name
(clay and grass events listed in `astrofoot/tennis/surface.py`, hard otherwise). It has no betting odds for tennis.

**Features** (all pre-match, built in time order):
- *Statistics*: Elo ratings overall and per surface, form (last 10 matches), sets won (last 30 sets), rest days,
  matches in the last 14 days, head-to-head, seeds, qualifier/wildcard, age, height, left-handedness, playing at home,
  best of 3 or 5, Grand Slam, round.
- *Astrology*: the natal chart at 12:00 UTC on the date of birth (birth times are not published, so no houses and the
  Moon is ±7°) against the sky at the start: solar return (birthday), transit Jupiter, Saturn and Mars to the natal Sun,
  Mars to Mars, Moon to Sun, Venus to Venus, Jupiter to Moon, Moon element, Sun element, and each player's Mars on the
  opponent's Sun.
- *Numerology*: life path, personal year, personal day, expression (name) number, and whether the personal or universal
  day matches the life path, or is a 1 or 8.

**Start times.** ESPN gives one scheduled time per match (never the actual start), and it moves with the order of play.
Pages show ESPN's latest scheduled time at the venue and in GMT, with a "moved" badge when it changed after the forecast
was sealed. ESPN writes "time not set yet" as midnight US Eastern (05:00 GMT in winter): those are treated as date-only,
forecast before that day begins at the venue, and charted for that date. A forecast is scored only if it was sealed
before the sealed start and before ESPN's final scheduled start (if the match was moved earlier).

**The match day is the venue's.** ESPN gives start times in GMT/UTC; the day's chart and numbers use the calendar
day at the venue (its timezone from the cities table, e.g. a 01:30 GMT match in Bogotá is still the 10th there), with the
day's planets at noon at the venue. About 98% of matches are placed; venues given only as a country with several
timezones (USA, Australia, …) fall back to the UTC day.

**Who is favoured for the day (date-only).** Birth times are rarely published and start times move, so astrology and
numerology use dates only: each player's chart for the date of birth against the sky on the match day (planets at
12:00 UTC; the Moon is left out, it moves too fast). Each player gets a traditional day score (Jupiter and Venus contacts
add, Saturn and hard Mars contacts subtract; numerology: personal day in harmony with the life path, 1 and 8 days, …) and
the higher score is "favoured for the day". Every contact (108) and number is also given to the machine, which learns its
own weights (logistic models and trees are tried), alone and on top of the statistics; they enter the expected figure only
where they improved unseen matches (ML model page shows the result).

**Odds and the expected figure.** ESPN has no tennis odds; The Odds API (the same free `ODDS_API_KEY`) prices about 50
tournaments: Grand Slams, Masters 1000, WTA 1000, the Finals, some 500s. Finding listed matches is free; buying a
tournament's odds costs one credit, at most every 12 hours, never below 150 credits left (kept for soccer). The margin-free
match chance is turned into set / first-set / at-least-one-set chances and blended with the model (60% odds) into the
**expected** figure shown everywhere. On Analyze you can type any bookmaker's odds yourself.

**Odds you enter yourself.** For a forecast sealed without odds, its match page has an Odds box: type a bookmaker's
decimal odds and every page (Forecasts, Live record, Top picks, My picks, the match page) uses them for that match, with
the expected figure recomputed exactly as the cycle would with odds ("your odds" badge; "add odds" links on matches
without). They are stored in your local database, never in the sealed ledger, whose seals still verify.

**Last 5 matches and head-to-head.** Each match page and Analyze show both players' last 5 completed matches and their
last 5 meetings (date, opponent, W/L, score, tournament), from the ESPN history before the match. They are also model
features (last-5 win share, sets won in the last 5, last-5 meetings, who won the last meeting).

**One id per player.** ESPN lists some players under two ids (41 cases, many re-keyed in 2021-22); ids with exactly
the same name and the same (or a missing) date of birth are merged, so ratings, form and head-to-head see the whole
record. Real namesakes with different dates of birth stay apart.

**ITF matches** come from the same API: ITF World Tennis Tour singles (M15/M25, W15–W100) are listed, forecast and sealed
automatically ("ITF" badge), with smaller sealed records (the day's astrology contacts are worked out again when shown).
There are about 200 ITF singles a day against 100 free requests, so results are fetched Challengers first, then the most
recent ITF matches; an ITF result not fetched within 3 days is void ("result not fetched"), unless you type it on the match
page. The request count follows the API's own usage figure.

**Challengers and team events (Live Tennis API, free tier).** ESPN has no Challengers, Hopman Cup, United Cup, Davis /
Billie Jean King Cup or Laver Cup. With a free key from livetennisapi.com saved as the GitHub secret `LIVETENNISAPI_KEY`,
each cycle lists upcoming Challenger singles and those team events, forecasts and seals them like the rest ("Challenger" /
"team event" badges), takes players' birthdays from the API for the astrology and numerology, and keeps a player's ESPN
history when the name matches. The free tier allows 100 requests a day: listings first (about 12 a day), then one look-up
per finished match to settle it, oldest first, keeping 10 spare. A result the quota has not reached yet can be typed on
the match page ("your result", stored on your computer until the official one arrives). Settled Challenger matches join
the history, so those players build up ratings over time.

**Matches you add.** ESPN covers the ATP and WTA tours (including WTA 125s) but not Challengers, ITF, Davis Cup or
exhibitions, and no other free source offers them for automated use. On Analyze, **Add this match to my tennis matches**
saves any match: it appears on Forecasts, Live record, Top picks and My picks with a "manual" badge; enter the score on its
match page once played (or mark it void / remove it). Played matches you add also count in the last five and
head-to-head tables (e.g. a Hopman Cup meeting ESPN does not list). Not sealed, never in the official track record; if ESPN later
lists the same match, the sealed forecast takes over.

**TBD.** ESPN lists draw slots before a player is known (a qualifier still to come) as "TBD". Those matches are not
forecast until both players are known; forecasts sealed with a TBD before this rule are shown as void.

**Top picks** (`/tennis/top`): tabs for sets, first set, match, at least one set and underdog to win a set, ranked by the
expected chance, with filters for day, tour, minimum probability, whether the day's astrology / numerology favour the
pick, and priced matches only; plus the live record of each view.

**Machine learning.** Four gradient-boosted models (win a set, first set, at least one set, match), trained on both
orientations of every match so neither player is favoured by order. Every retrain fine-tunes: it compares statistics
alone with statistics + astrology, + numerology and + both on the latest 12 months held out, and keeps astrology or
numerology only if it lowers the held-out log loss by more than one standard error. It then tunes the settings, checks
the last seasons walk-forward against a plain Elo rating, and refits on everything as a new version. The model is
retrained weekly on GitHub (workflow `tennis`, Tuesdays: refreshes the history and players, then trains); on the ML model
page, **Retrain on this computer** runs the same training locally, and **Rebuild data + retrain on GitHub** starts the
workflow (needs the Update now token).

**Live record** (`/tennis/live`): every sealed tennis forecast, newest first, with its seal check; the track record
(sets, first set, match, underdog winning a set); filters for dates, status, tour, surface, player, tournament, market,
right/wrong, minimum probability, level (ATP/WTA tour, WTA 125, Challenger, ITF women / men, team events, all women's or men's), the day's astrology and numerology (including "both favour the same player"), and priced matches; the statistics model, the
expected figure and the odds compared on settled matches; calibration of set picks; and the same Update now / Get latest
results buttons as soccer (one GitHub run covers both).

**My picks** (`/tennis/mypicks`): tennis slips, kept apart from the soccer ones. Choose a day, tick matches and an outcome
for each (either player to win the match, the first set, or at least one set; most likely preselected, each with its
expected probability and whether the day's astrology and numerology favour that player), add them to a slip, edit later.
Scored once played; presentation report and CSV like soccer's.

Commands: `python scripts/tennis.py build` (history + players), `train` (features + training), `cycle` (live forecasts).

## Soccer day reading (astrology and numerology for the match day)

Each soccer match page (live record and games analysed by hand on Analyze) has a **Day reading** card: date-only astrology and numerology of both clubs' founding dates
(their "birth", from the founding-charts table; only dates known to the day) for the match day at the venue, as for
tennis players. The *day* reading says which team the day favours; the *scoring* reading says whether it favours each
team to score (Mars and Jupiter contacts to the natal Mars and Sun add, Saturn subtracts; numerology: active personal days
1, 3, 5, 8, 9 add, 4 and 7 subtract). Lists show a one-line "Day:" note under each game, and Top picks (Match result and
Home or away goal tabs) can filter on whether astrology / numerology / both favour the pick.

Tested on 91,525 past team-matches (391 clubs; `python scripts/teamday_research.py`, results in
`data/models/teamday.json`): teams the reading favoured to score scored as often as those it disfavoured, both in line
with the odds, and a model trained on every contact and number did slightly worse than the odds on unseen seasons. The
reading is shown for interest; forecasts do not use it. On Analyze, a founding chart you enter or pick for a team is
used for its day reading; otherwise founding dates are looked up by each GitHub cycle and kept in
`data/ref/team_founding_days.json` (about half the teams have one known to the day). Women's teams (Women section: the
Women page, its Live record, Top picks, My picks and Dataset) are looked up as women's teams ("Chelsea (women)",
"Chelsea Women", "Frauen", "Femenil", …, kept under "W:<team>"), never with the men's club's date.

**Day reading on/off.** The "Day reading: on/off" button in the soccer header shows or hides the day reading (cards,
"Day:" notes and filters) on every soccer page; the choice is remembered on this computer.

**Youth games and national teams.** U17–U23 competitions and sides (e.g. UEFA U21 qualifiers, "Liverpool U21") are
included when ESPN prices them, always under their own names ("England U21"), never matched to the senior team or its
history ("youth" badge). A youth side with no ground of its own plays at its senior team's ground; a national team
whose stadium is not found is placed in its home city from TheSportsDB (free public key), else the country's largest
city. A national team's ground is never placed abroad unless ESPN's own venue city confirms it (teams banned from their
own stadiums do play "home" games elsewhere); map searches that return a namesake stadium in another country are
rejected. International and club friendlies are forecast
when ESPN prices them (only some are: games without odds cannot be forecast).

## Women's football (separate section)

The **Women** page has its own forecasts, sealed before kickoff and scored like the men's, in their own ledger
(`ledger/women/`: predictions, results, `TRACK_RECORD.md`). They never enter the men's track record or figures,
and the men's pipeline never forecasts women's competitions. The Live record, Top picks, My picks and Dataset each have a
separate **Women** section (Dataset: every women's forecast with filters and a CSV export, `/dataset/women.csv`; there is
no women's research corpus) (Men / Women buttons at the top): every Top picks tab, including the Form check (women's results only), works
on the women's games alone.

- **Sources:** ESPN. Once a day the cycle discovers the women's senior competitions with home/draw/away odds
  (`ledger/women/espn_competitions.json`; seeded with the Women's Champions League, WSL, Liga F, Première Ligue,
  Frauen-Bundesliga, Serie A Women, NWSL, Liga MX Femenil, Damallsvenskan and A-League Women; youth and college left out).
  Results from ESPN; void after 3 days without one.
- **Grounds:** only the venue ESPN names for each game (women's teams often play away from the men's stadiums), cached by
  venue in `ledger/women/venues.json`; never the men's venue tables.
- **Form checks** use women's results only (ESPN lists clubs by their plain names, so men's results would otherwise mix in).
- **Caveat:** Engine 4 and the goal-market recalibrations were trained on men's football, so the women's probabilities
  rest mainly on the odds; the women's track record shows how well that holds up.

## More leagues and cups (ESPN and The Odds API)

A forecast needs a fixture **with bookmaker odds** (the market baseline behind every probability) and a venue. Besides
football-data.co.uk, the cycle now uses:

- **ESPN's public scoreboard** (free, no key; DraftKings odds), checked first: games in our leagues not listed yet, and
  leagues and cups football-data.co.uk does not cover: Colombia, Ecuador, Paraguay, Peru, Uruguay, Chile, Australia,
  Brazil Serie B, Saudi Arabia; the FA Cup, EFL Cup, Copa del Rey, DFB-Pokal, Coppa Italia, Coupe de France, Copa
  Libertadores, Copa Sudamericana and CONCACAF Champions Cup. Only games with home/draw/away odds are used; the
  over/under 2.5 price is taken when ESPN's line is 2.5.
- **The Odds API** (credits) afterwards, for what is still missing, now also covering the A-League, Brazil Serie B, Chile,
  the Libertadores and Sudamericana, the FA Cup, EFL Cup, DFB-Pokal and Copa del Rey (women's competitions are left out:
  the models were trained on men's league football).

**Discovery.** ESPN publishes odds for a competition only around its match days, so once a day the cycle scans every
men's competition ESPN lists (about 185) and remembers each one that shows home/draw/away odds
(`ledger/espn_competitions.json`); from then on its fixtures are checked every cycle. A few are checked from the start
(Bolivia, Venezuela, Costa Rica, Honduras, Guatemala, El Salvador, Panama, Canada, Argentina's Primera Nacional, Liga de
Expansión MX, Chile and Colombia's second divisions, the EFL Trophy, the Nations League). These appear as their own
leagues (division codes such as `X:bol.1`). Youth (U21, U23…), college and women's competitions are left out, by
ESPN code and by name, case-insensitively (Women's, Frauen, Féminine, Femenil, Damallsvenskan, Liga F, NWSL…).

**The Americas.** Already forecast: MLS, Liga MX, Brazil Série A and Argentina (football-data.co.uk); Brazil Série B,
Colombia, Ecuador, Paraguay, Peru, Uruguay and Chile, the Libertadores, Sudamericana and CONCACAF Champions Cup (ESPN /
The Odds API). Checked every cycle and forecast as soon as bookmakers price them: Bolivia, Venezuela, Central America,
Canada, Argentina's Primera Nacional and Primera B, Liga de Expansión MX, the Chilean, Colombian and Uruguayan second
divisions, the USL Championship and League One, the Copa Argentina, Copa do Brasil, Copa Chile, Copa Colombia, Copa Bolivia,
U.S. Open Cup, Recopa, Leagues Cup, the Brazilian state championships and the CONCACAF Nations League. College (NCAA) and
women's competitions are left out.

**Oceania and the Middle East.** Australia's A-League and the Saudi Pro League are forecast (The Odds API and ESPN);
the AFC Champions League Elite, AFC Champions League Two and Saudi King's Cup are checked every cycle and forecast as
soon as ESPN prices them. No free source found carries the UAE, Qatari, Iranian, Iraqi, Jordanian, Kuwaiti or New
Zealand leagues.

**More of Europe.** ESPN adds the Dutch Eerste Divisie and the KNVB Cup, Taça de Portugal, Scottish Cup, League Cup and
Challenge Cup; The Odds API adds Germany's 3. Liga and Sweden's Superettan and also prices the Coupe de France and Coppa
Italia. Results for competitions only The Odds API covers (3. Liga, Superettan) come from its scores endpoint (2 credits a
call, at most every 12 hours per competition and only while a forecast waits). No free source found prices the Czech,
Croatian, Serbian, Hungarian, Bulgarian, Slovak, Ukrainian, Cypriot or Israeli leagues; national-team games come only
from ESPN (which gives the venue).

**Asia and Africa.** Free odds are scarce here. Japan and China come from football-data.co.uk; The Odds API prices the
K League 1, Saudi Pro League and Africa Cup of Nations (used automatically whenever they are in season); ESPN lists many
Asian and African competitions (AFC and CAF cups and qualifiers, India, South Africa, Saudi Arabia) but, as of November
2026, without odds, and discovery will pick any of them up the day ESPN starts pricing them. No free source found
publishes odds for African domestic leagues (Egypt, Morocco, Nigeria…), so those cannot be forecast.

These competitions are handled like the UEFA ones: names matched strictly (cups use every club name we know), grounds
found from our tables, the stadium ESPN names (its Wikipedia page) or its city, then a search, and cached in
`ledger/european_venues.json`; results from ESPN (and football-data.org where it covers them); void after 3 days without a
result. A game never gets two forecasts across sources (same competition, kickoff within 6 hours, matching names).
Worldwide lists such as Flashscore also include women's, youth and many lower or regional leagues without published odds,
which cannot be forecast this way.

## European competitions (Champions League, Europa League, Conference League)

football-data.co.uk has no files for club competitions, so these come only from the secondary sources:

- **Fixtures and odds**: The Odds API (`ODDS_API_KEY`), games kicking off within 30 hours. For these nights the
  over/under 2.5 market is bought too (2 credits per competition request instead of 1), so every goal
  prediction has a price. Division codes: `UCL`, `UEL`, `UECL`.
- **Team names**: clubs from our leagues get their football-data.co.uk name (e.g. "Man United"), so they line
  up with their league games; clubs from elsewhere keep The Odds API's name.
- **Ground**: our venue tables first; clubs outside our leagues are looked up on Wikipedia, then
  OpenStreetMap. Each club's ground is cached in `ledger/european_venues.json` (committed, so it never
  changes silently); a club whose ground cannot be found is skipped and listed in the run log.
- **Results**: football-data.org (Champions League) and ESPN (all three). Knockout ties that go to extra
  time are scored on the 90-minute result (ESPN's per-half scores). No primary source will confirm these,
  so a European game with no result from either source 3 days after kickoff is recorded as void.
- The models were trained on league football only; European games are forecast the same way (market
  baseline plus the classical engines), and the track record will show whether that holds.

## Top picks: Summary

The first Top picks tab, **Summary**, lists each game of the day once with its **single most likely outcome**
across the markets you tick (match result, double chance, over/under 1.5, over/under 2.5, home or away goal,
both teams to score), ranked by that probability, with every other market's prediction alongside and ✓/✗ once
played. Each market is calibrated on its own, so the "expected" hit rate is an honest target. With every
market ticked, the safest calls (a team to score, over 1.5, double chance) usually win; untick them to see
each game's most likely bolder outcome. The note under the table shows which markets the day's picks came from.

## My picks

The **My picks** tab (next to Top picks): choose a day and its games load from the live record and your dataset
(each once). Tick the games you want and choose an outcome for each from a list of every market's outcomes
(home/draw/away, double chance, over/under 1.5 and 2.5, each team to score or not, both teams to score or not),
each with its calibrated probability; the most likely one is preselected.

**Men / Women** buttons at the top switch section. The Women section lists the women's forecasts and keeps its own
slips and scores, apart from the men's. The report and CSV cover one section, or both together (CSV has a
`section` column).

**Expected-goals filter.** Above the day's games: *Expected goals (from the odds)* any / 0.8+ / 1.0+ / 1.2+ / 1.5+ / 2.0+,
*for* either team, the home team, the away team or the team backed by 2+ engines. Each game shows both teams' expected
goals (the qualifying one in bold), with a note beneath the game naming the team 2 or 3 of the engines back (e.g. "2/3
engines back Juarez"; hover for both teams' counts). **Engines backing a team** (any, 2/3 or 3/3,
3/3, 2/3, 1/3, 0/3) keeps games where one of the teams has that many of the 3 engines behind it. Filters only narrow the
games list (never your slips) and stay set while you switch slips, add games or save.

**Slips.** A day can have any number of slips ("Slip 1", "Slip 2", or a name you give; rename or delete them any
time). Choose a slip, tick games and **Add selected games** to it (its earlier picks are kept). A game can be on
several slips with different outcomes, once per slip. In the open slip every outcome stays editable, a game can be
removed, and **Save changes** applies both. The day's slip table shows each slip's picks, the chance all its picks
come in, picks won, and the slip's state: *won* only if every pick won, *lost* as soon as one loses (void picks
are left out). Slips are stored in your local database (`data/app.sqlite3`, tables `my_slips` and
`my_slip_picks`); picks saved before slips existed were moved into "Slip 1" of their day, and the old table is kept
as `my_picks_v1_backup`. The
*Astrology agrees* column counts the classical engines whose predicted score agrees with your chosen outcome
(for a match-result pick, the same count as the Live record).

**Presentation report** (`/mypicks/report`, buttons on My picks: this day, all days, or a date range): a
print-ready page (Print → Save as PDF) with nothing left out: the slips (picks, chance all come in, result), summary (scored hit rate vs expected, picks still
to play and the chance they all come in, picks not scored and why), results by market next to the same market's
historical backtest, results by astrology agreement, and every pick in full: kickoff in UTC and venue-local time,
the pick and its probability, each engine's predicted score and call and whether it agrees, every market's
probabilities with the pick highlighted, the odds and their source, venue, source (sealed live forecast with its
SHA-256, or manual), model version, when the pick was made, the result and its source; then the method and
caveats; picks are grouped by slip. **CSV** (`/mypicks/export.csv`): the same detail, one row per pick (with its slip),
51 columns.

Played games are marked ✓/✗ and scored: hit rate vs the rate the picks' probabilities expected, for the day and
all days, plus the chance that all of a day's picks come in. A pick made after kickoff is marked and not scored.

## Top picks: Form check

For every game where **at least 2 of the 3 classical engines back the same team to win** (favourite or underdog), the
**Form check** tab (and a section on the game's page) analyses how that team has been scoring, using only games
before kickoff:

- its last 5 **home** games if it plays at home, or last 5 **away** games if away;
- its last 5 games **overall**;
- its last 3 **meetings with this opponent**;
- and, for context, how the **opponent** has been conceding (last 5 at its venue type, last 5 overall).

Each window shows goals per game, games scored in, 2+ goals, W/D/L and every game behind the numbers. A transparent
blend of these gives a form estimate of the team's expected goals, P(scores) and P(2+), beside the market's calibrated
P(scores); the result is marked once played. Filters: day, engines backing the team (2/3 or 3/3 by default; also exactly
0/3, 1/3, 2/3 or 3/3, so teams the engines do not back can be compared), team is favourite or underdog,
and **expected goals (from the odds)**: 0.8+, 1.0+, 1.2+, 1.5+ or 2.0+. Expected goals is the backed team's scoring rate
implied by the match odds, the factor that best predicts whether a backed team scores; historically backed teams scored
71.7% overall, 78.2% at 1.0+, 86.4% at 1.5+ and 91.6% at 2.0+ (`by_xg` in `data/models/form.json`), while the number of
engines agreeing and the engines' strength made no difference: at every expected-goals level, teams with 0, 1, 2 or 3
engines behind them scored at the same rate within about a point (`by_agree` in `data/models/form.json`, shown on the tab).

The **Live record** and the other Top picks tabs (Summary and every market) have the same **expected goals** filter, for either team, the home
team, the away team or the team backed by 2+ engines; each game then shows both teams' expected goals. Every game in the Live record and in the Top picks
tables also shows an **xG home · away** column and, beneath the game, which team 2 or 3 of the engines back (e.g. "2/3
engines back Juarez"; hover for both teams' counts), as in My picks.

**Honest finding** (`research.py overunder` → `data/models/form.json`): over 201,138 historical team-games, walk-forward,
adding the form estimate to the market does not improve the prediction of whether a team scores (log loss 0.5602 both
ways; form alone 0.5780), and the same holds for teams backed by 2+ engines. When form says a team should score much more
than the odds imply, it scored *less* often. The page shows this: the form figures are context, not an edge.

Data: the research corpus, plus every result of the current and previous season from football-data.co.uk (the cycle
refreshes `ledger/recent_results.csv` daily, because the corpus lags), plus settled live games.

## One list of games: manual and automatic, no duplicates

- **Live record and Top picks** list the games you add on the Analyze page alongside the automatic forecasts,
  marked *manual*, with every filter, prediction and score. A **Source** filter shows either kind alone. Only the
  automatic forecasts are sealed on GitHub, so the official track record (tiles and `TRACK_RECORD.md`) counts
  those alone. A historical game you add after it was played is never counted as a pre-kickoff forecast.
- **Dataset** has one *Forecast games* table: every live forecast (pending, completed or void) and every manual
  game, filterable by source, status, league and team.
- **No duplicates.** Two entries are the same game when kickoffs are within 6 hours and both clubs' names match
  (either way round). Analyze refuses to save a game that is already in your dataset or the live record and
  opens the existing entry instead. A game you analysed before the live record forecast it is shown once,
  as the sealed live forecast, with a link to your analysis (`astrofoot/merged.py`).

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
