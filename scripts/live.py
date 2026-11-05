"""Live track record CLI.

  python scripts/live.py cycle                 # settle finished matches, commit upcoming ones, rebuild report
  python scripts/live.py commit [--horizon 4]  # predictions for fixtures kicking off within N days
  python scripts/live.py settle                # fetch results for predicted matches that have finished
  python scripts/live.py report                # rebuild ledger/TRACK_RECORD.md
  python scripts/live.py verify                # check every ledger record's SHA-256

Offline / manual sources: --fixtures FILE.csv and --results FILE.csv [FILE.csv ...] take
football-data.co.uk-format files instead of downloading them.
After `cycle`, commit and push the ledger/ directory *before* the earliest kickoff.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from astrofoot import fixtures2, geo, live, results2, results_espn, venues  # noqa: E402


def european_pool(fixtures: list[dict], preds: list[dict]) -> set[str]:
    """football-data.co.uk names of top-division clubs we know (current fixtures, earlier forecasts), so a
    European entrant from one of our leagues gets the same name, and ground, as in its league. Lower
    divisions are left out: their clubs do not play in Europe, and their names collide with ones that do
    (Red Star Paris / Red Star Belgrade, Lincoln City / Lincoln Red Imps)."""
    return {n for r in fixtures + preds if r["division"] in live.TOP_TIER for n in (r["home"], r["away"])}


class EuropeanGrounds:
    """Home ground of a club in a European tie: our venue tables first (stadium, or the club's own league),
    then Wikipedia / OpenStreetMap for clubs outside our leagues. Lookups are cached in the ledger
    (european_venues.json), so a club's ground is found once and stays the same."""

    def __init__(self, ledger: Path, preds: list[dict]):
        self.path = ledger / "european_venues.json"
        try:
            self.cache = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.cache = {}
        self.div_of = {}
        for r in preds:
            if r["division"] not in live.EUROPEAN:
                self.div_of.setdefault(r["home"], r["division"])

    def __call__(self, team: str):
        if team in self.cache:
            c = self.cache[team]
            return (c["lat"], c["lon"], c["source"])
        loc = None
        try:
            st = geo.stadiums()
            if team in st:
                loc = (*st[team], "stadium")
        except Exception:  # noqa: BLE001
            pass
        if loc is None and team in self.div_of:
            loc = geo.resolve(team, self.div_of[team])
        if loc is None:
            for fn, src in ((venues.wikipedia_ground, "wikipedia"), (venues.nominatim_ground, "openstreetmap")):
                try:
                    hit = fn(team)
                except Exception:  # noqa: BLE001
                    hit = None
                if hit:
                    loc = (hit[0], hit[1], f"{src}: {hit[2]}")
                    break
        if loc is None:
            return None             # not cached: tried again next cycle
        self.cache[team] = {"lat": loc[0], "lon": loc[1], "source": loc[2]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        return loc


def load_fixtures(a, now) -> list[dict]:
    if a.fixtures:
        return live.parse_fixtures(live.read_csv_bytes(Path(a.fixtures).read_bytes()))
    out, errors = [], []
    for url in live.FIXTURE_URLS:
        try:
            out += live.parse_fixtures(live.fetch_csv(url))
        except Exception as e:  # noqa: BLE001 - report every source failure, keep going
            errors.append(f"{url}: {type(e).__name__}: {e}")
    if errors:
        print("fixture sources unavailable:\n  " + "\n  ".join(errors), file=sys.stderr)
    key = fixtures2.token()
    if key:
        import pandas as pd
        local_date = lambda ko: pd.Timestamp(ko).tz_convert(live.TIMEZONE_OF_SOURCE_TIMES).strftime("%Y-%m-%d")  # noqa: E731
        voided = {k for k, v in live.read_results(a.ledger).items() if v.get("void")}
        preds = [r for r in live.read_predictions(a.ledger) if r["match_key"] not in voided]
        out += fixtures2.extra_fixtures(out, now, a.horizon, a.ledger, fixtures2.Client(key), live.fetch_csv,
                                        live.results_url, live.match_key, local_date, preds,
                                        venue_of=EuropeanGrounds(a.ledger, preds),
                                        european_pool=european_pool(out, preds))
    else:
        print("extra fixtures: set ODDS_API_KEY to add games football-data.co.uk has not listed yet")
    if not out and errors:
        raise SystemExit("No fixtures could be downloaded (is www.football-data.co.uk allowed by the network policy?)")
    return out


def load_results(a, now) -> tuple[dict, dict]:
    res, latest = {}, {}

    def take(df):
        res.update(live.parse_results(df))
        for d, day in live.latest_dates(df).items():
            latest[d] = max(day, latest.get(d, ""))
    if a.results:
        for f in a.results:
            take(live.read_csv_bytes(Path(f).read_bytes()))
        return res, latest
    for url in sorted(live.needed_result_urls(a.ledger, now)):
        try:
            take(live.fetch_csv(url))
        except Exception as e:  # noqa: BLE001
            print(f"results unavailable: {url}: {type(e).__name__}: {e}", file=sys.stderr)
    for k in res:
        res[k]["source"] = live.PRIMARY
    # Faster sources for matches the primary has not published yet; the primary later confirms or corrects them
    settled = live.read_results(a.ledger)
    waiting = [r for r in live.read_predictions(a.ledger)
               if r["match_key"] not in settled and r["match_key"] not in res
               and datetime.fromisoformat(r["kickoff_utc"]) + timedelta(hours=2) < now]
    pending = [r for r in waiting if r["division"] in results2.COMPETITION_DIV.values()]
    tok = results2.token()
    if pending and tok:
        days = [datetime.fromisoformat(r["kickoff_utc"]).date() for r in pending]
        try:
            # a day either side: the API's dateTo is not inclusive, and kickoff times are checked anyway
            got = results2.fetch(min(days) - timedelta(days=1), max(days) + timedelta(days=1), tok)
            per = {}
            for m in got:
                c = (m.get("competition") or {}).get("code")
                per[c] = per.get(c, 0) + 1
            print(f"football-data.org returned {len(got)} finished match(es): "
                  + (", ".join(f"{c} {n}" for c, n in sorted(per.items(), key=lambda x: str(x[0]))) or "none"))
            found, notes = results2.match_results(pending, got)
            res.update(found)
            print(f"football-data.org: {len(found)} of {len(pending)} pending top-league result(s) found")
            for n in notes:
                print("  unmatched:", n)
        except Exception as e:  # noqa: BLE001
            print(f"football-data.org unavailable: {type(e).__name__}: {e}", file=sys.stderr)
    elif pending:
        print(f"{len(pending)} pending top-league match(es) could settle faster with FOOTBALL_DATA_ORG_TOKEN set")
    rest = [r for r in waiting if r["match_key"] not in res]
    if rest:
        found, notes, counts = results_espn.match_results(rest)
        res.update(found)
        print("espn.com returned finished match(es): " + (", ".join(f"{d} {n}" for d, n in counts.items()) or "none"))
        print(f"espn.com: {len(found)} of {len(rest)} remaining pending result(s) found")
        for n in notes:
            print("  unmatched:", n)
    return res, latest


def diagnose(a, now):
    """What do the source files actually contain? (read-only; prints a report, writes nothing)"""
    import pandas as pd
    print(f"now (UTC): {now:%Y-%m-%d %H:%M}")
    for url in live.FIXTURE_URLS:
        try:
            df = live.fetch_csv(url)
            fx = live.parse_fixtures(df)
            ko = sorted(f["kickoff_utc"] for f in fx)
            soon = [f for f in fx if now < datetime.fromisoformat(f["kickoff_utc"]) <= now + pd.Timedelta(days=a.horizon)]
            print(f"FIXTURES {url}: {len(df)} rows, {len(fx)} usable; kickoffs {ko[0][:16] if ko else '-'} .. "
                  f"{ko[-1][:16] if ko else '-'}; within {a.horizon:g} days: {len(soon)}")
            if len(df) and not fx:      # layout we cannot read: show it
                print(f"  columns: {list(df.columns)}")
                print(f"  first row: {df.iloc[0].to_dict()}")
        except Exception as e:  # noqa: BLE001
            print(f"FIXTURES {url}: unavailable ({type(e).__name__}: {e})")
    settled = live.read_results(a.ledger)
    pending = [r for r in live.read_predictions(a.ledger) if r["match_key"] not in settled]
    print(f"PENDING forecasts: {len(pending)}")
    print("EXTRA FIXTURES the-odds-api.com: " + ("key configured" if fixtures2.token() else
          "no key (set the ODDS_API_KEY secret to add games football-data.co.uk has not listed yet)"))
    print("SECOND SOURCE football-data.org: " + ("key configured" if results2.token() else
          "no key (set the FOOTBALL_DATA_ORG_TOKEN secret to settle top-league results faster)"))
    files = {}
    for rec in pending:
        ko = datetime.fromisoformat(rec["kickoff_utc"])
        url = live.results_url(rec["division"], ko)
        if url not in files:
            try:
                df = live.fetch_csv(url)
                dates = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
                files[url] = (df, dates)
                print(f"RESULTS {url}: {len(df)} rows, latest match date {dates.max():%Y-%m-%d}")
            except Exception as e:  # noqa: BLE001
                files[url] = None
                print(f"RESULTS {url}: unavailable ({type(e).__name__}: {e})")
        if files[url] is None:
            continue
        df, dates = files[url]
        day = ko.astimezone(live.ZoneInfo("Europe/London")).date()     # source dates are UK calendar dates
        same_day = df[dates.dt.date == day]
        exact = same_day[(same_day.HomeTeam.str.strip() == rec["home"]) & (same_day.AwayTeam.str.strip() == rec["away"])]
        state = ("in file" + ("" if "FTHG" in df and pd.notna(exact.iloc[0].get("FTHG")) else " but no score yet")) if len(exact) \
            else (f"NOT in file; that day lists: {', '.join((same_day.HomeTeam + ' v ' + same_day.AwayTeam).head(4))}"
                  if len(same_day) else "NOT in file (no matches on that date yet)")
        print(f"  {rec['kickoff_utc'][:16]} {rec['division']:4} {rec['home']} v {rec['away']}: {state}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cycle", "commit", "settle", "report", "verify", "diagnose"])
    ap.add_argument("--fixtures")
    ap.add_argument("--results", nargs="*")
    ap.add_argument("--horizon", type=float, default=4.0)
    ap.add_argument("--ledger", type=Path, default=live.LEDGER)
    ap.add_argument("--now", help="ISO timestamp (testing/replay only)")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    if a.cmd == "diagnose":
        diagnose(a, now)
        return
    if a.cmd == "verify":
        recs = live.read_predictions(a.ledger) + list(live.read_results(a.ledger).values())
        bad = [r.get("match_key") for r in recs if not live.verify(r)]
        print(f"{len(recs) - len(bad)}/{len(recs)} records verify" + (f"; FAILED: {bad}" if bad else ""))
        raise SystemExit(1 if bad else 0)
    if a.cmd in ("cycle", "settle"):
        res, latest = load_results(a, now)
        n = live.settle(res, now, a.ledger, latest=latest)
        print(f"settled {n} match(es)")
    if a.cmd in ("cycle", "commit"):
        r = live.commit(load_fixtures(a, now), now, a.horizon, a.ledger)
        print(f"committed {r['committed']} prediction(s)")
        for s in r["skipped"]:
            print("  skipped:", s)
    rep = live.report(a.ledger)
    live.write_report(rep, a.ledger)
    print(f"report: {rep['settled']} settled, {rep['pending']} pending")


if __name__ == "__main__":
    main()
