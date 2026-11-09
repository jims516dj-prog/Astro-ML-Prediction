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
from astrofoot import fixtures2, fixtures_espn, form, geo, live, results2, results_espn, venues  # noqa: E402


def recent_names(ledger: Path) -> dict[str, set[str]]:
    """football-data.co.uk names per division from ledger/recent_results.csv (this and last season)."""
    p = ledger / "recent_results.csv"
    out: dict[str, set[str]] = {}
    if p.exists():
        import pandas as pd
        r = pd.read_csv(p, usecols=["division", "home", "away"])
        for d, g in r.groupby("division"):
            out[d] = set(g.home) | set(g.away)
    return out


def european_pool(fixtures: list[dict], preds: list[dict], ledger: Path | None = None) -> set[str]:
    """football-data.co.uk names of the clubs we know (every league we cover: fixtures, forecasts, this and last
    season's results), so a club in a cup or a European tie gets the same name, and ground, as in its league.
    Matching is strict (every word of the other source's name must be in ours, one club only), so Red Star
    Belgrade, Lincoln Red Imps or Inter Club d'Escaldes are not taken for Red Star, Lincoln or Inter."""
    names = {n for r in fixtures + preds if r["division"] not in live.NO_PRIMARY for n in (r["home"], r["away"])}
    for d, ns in (recent_names(ledger) if ledger else {}).items():
        names |= ns
    return names


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
            if r["division"] not in live.MULTI_CLUB:
                self.div_of.setdefault(r["home"], r["division"])

    def __call__(self, team: str, division: str | None = None, hint: dict | None = None):
        """hint: the venue as the fixtures source gives it ({name, city, country}), used before searching."""
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
        if loc is None and division in geo.DIVISION_COUNTRY and division not in live.MULTI_CLUB:
            try:
                loc = geo.resolve(team, division)          # a league's own country: the club's city
            except Exception:  # noqa: BLE001 - venue tables not downloaded
                loc = None
        city_ll = geo.city_lookup(hint.get("country"), hint.get("city")) if hint else None
        if loc is None and hint and hint.get("name"):
            name, city = hint["name"], hint.get("city") or ""
            for fn, q, src in ((venues.wikipedia, name, "wikipedia"),                 # the stadium's own page
                               (venues.nominatim_stadium, f"{name}, {city}" if city else name, "openstreetmap")):
                try:
                    hit = fn(q)
                except Exception:  # noqa: BLE001
                    hit = None
                # a hit far from the city ESPN gives is a namesake elsewhere
                if hit and (city_ll is None or venues.km(city_ll, hit[:2]) < 40):
                    loc = (hit[0], hit[1], f"{src}: {hit[2]}")
                    break
        if loc is None and city_ll:
            loc = (city_ll[0], city_ll[1], f"city: {hint.get('city')}")
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
    import pandas as pd
    local_date = lambda ko: pd.Timestamp(ko).tz_convert(live.TIMEZONE_OF_SOURCE_TIMES).strftime("%Y-%m-%d")  # noqa: E731
    voided = {k for k, v in live.read_results(a.ledger).items() if v.get("void")}
    preds = [r for r in live.read_predictions(a.ledger) if r["match_key"] not in voided]
    grounds = EuropeanGrounds(a.ledger, preds)
    rn = recent_names(a.ledger)
    known_of = lambda d: ({n for r in out + preds if r["division"] == d for n in (r["home"], r["away"])}  # noqa: E731
                          | rn.get(d, set()))
    # ESPN first: free (DraftKings odds); The Odds API after it, for what is still missing (costs credits)
    try:
        fixtures_espn.discover(now, a.ledger / "espn_competitions.json")      # once a day: competitions with odds
    except Exception as e:  # noqa: BLE001
        print(f"espn.com discovery failed: {type(e).__name__}: {e}", file=sys.stderr)
    try:
        out += fixtures_espn.extra_fixtures(out, now, a.horizon, live.match_key, local_date, preds, known_of,
                                            european_pool(out, preds, a.ledger), grounds)
    except Exception as e:  # noqa: BLE001 - an unofficial feed: never block the cycle
        import traceback
        print(f"espn.com fixtures unavailable: {type(e).__name__}: {e}\n" + "".join(traceback.format_exc(limit=4)),
              file=sys.stderr)
    key = fixtures2.token()
    if key:
        out += fixtures2.extra_fixtures(out, now, a.horizon, a.ledger, fixtures2.Client(key), live.fetch_csv,
                                        live.results_url, live.match_key, local_date, preds,
                                        venue_of=grounds, european_pool=european_pool(out, preds, a.ledger))
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


PROBE_ESPN = ["eng.1", "eng.2", "eng.3", "eng.4", "eng.5", "sco.1", "sco.2", "ger.1", "ger.2", "ger.3", "ita.1", "ita.2",
              "esp.1", "esp.2", "fra.1", "fra.2", "ned.1", "ned.2", "bel.1", "por.1", "tur.1", "gre.1", "aut.1", "sui.1",
              "den.1", "nor.1", "swe.1", "fin.1", "irl.1", "pol.1", "rou.1", "rus.1", "cze.1", "hun.1", "cro.1", "srb.1",
              "ukr.1", "bul.1", "cyp.1", "isr.1", "usa.1", "usa.2", "mex.1", "mex.2", "arg.1", "bra.1", "bra.2", "chi.1",
              "col.1", "per.1", "ecu.1", "uru.1", "par.1", "aus.1", "jpn.1", "kor.1", "chn.1", "ksa.1", "egy.1", "rsa.1",
              "mar.1", "ind.1", "eng.league_cup", "eng.fa", "esp.copa_del_rey", "ger.dfb_pokal", "ita.coppa_italia",
              "fra.coupe_de_france", "uefa.champions", "uefa.europa", "uefa.europa.conf", "conmebol.libertadores",
              "conmebol.sudamericana", "concacaf.champions", "fifa.friendly", "uefa.nations"]


def probe_sources(now):
    """Diagnose only: which free sources could list more fixtures *with odds* (a forecast needs odds)."""
    import json
    import urllib.request
    from datetime import timedelta
    key = fixtures2.token()
    if key:
        try:
            sports = fixtures2.Client(key).get("/sports")
            soccer = sorted(s["key"] for s in sports if s.get("active") and s["key"].startswith("soccer"))
            known = set(fixtures2.SPORT_DIV)
            print(f"ODDS API active football competitions: {len(soccer)}; not yet used: "
                  + ", ".join(k for k in soccer if k not in known))
        except Exception as e:  # noqa: BLE001
            print("ODDS API sports list unavailable:", type(e).__name__, e)
    d0, d1 = now.date(), (now + timedelta(days=2)).date()
    tot_ev = tot_odds = 0
    sample = None
    for slug in PROBE_ESPN:
        evs, err = [], None
        for day in (d0, d0 + timedelta(days=1)):          # ESPN refuses date ranges: one day at a time
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={day:%Y%m%d}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (astro-football-research)"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    evs += json.loads(r.read()).get("events", [])
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__} {getattr(e, 'code', '')}"
        if err and not evs:
            print(f"ESPN {slug}: unavailable ({err})")
            continue
        upcoming = [e for e in evs if (e.get("status") or {}).get("type", {}).get("state") == "pre"]
        with_odds = [e for e in upcoming if (e.get("competitions") or [{}])[0].get("odds")]
        tot_ev += len(upcoming)
        tot_odds += len(with_odds)
        if with_odds and sample is None:
            sample = (slug, with_odds[0]["competitions"][0]["odds"][0])
        if upcoming:
            print(f"ESPN {slug}: {len(upcoming)} upcoming, {len(with_odds)} with odds")
    print(f"ESPN total: {tot_ev} upcoming games in the next 2 days, {tot_odds} with odds")
    for slug in ("esp.copa_del_rey", "col.1", "ecu.1", "par.1", "esp.2"):     # raw odds shape, for the parser
        try:
            evs = []
            for k in (0, 1):
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={(d0 + timedelta(days=k)):%Y%m%d}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (astro-football-research)"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    evs += json.loads(r.read()).get("events", [])
            for e in evs[:1]:
                c = (e.get("competitions") or [{}])[0]
                o = c.get("odds")
                print(f"ESPN RAW {slug}: odds type {type(o).__name__}, len {len(o) if hasattr(o, '__len__') else '-'}")
                for i, x in enumerate((o or [])[:2]):
                    if not isinstance(x, dict):
                        print(f"  odds[{i}]:", json.dumps(x)[:200])
                        continue
                    print(f"  odds[{i}] keys:", sorted(x))

                    def strip(v):
                        if isinstance(v, dict):
                            return {k: strip(w) for k, w in v.items() if k not in ("link", "links", "tracking", "logos")}
                        return v
                    for k in sorted(x):
                        if any(t in k.lower() for t in ("home", "away", "moneyline", "spread", "pointspread")):
                            print(f"    {k}:", json.dumps(strip(x[k]))[:700])
        except Exception as e:  # noqa: BLE001
            print(f"ESPN RAW {slug}: {type(e).__name__} {e}")
    if sample:
        print("ESPN odds sample", sample[0], json.dumps(sample[1])[:1500])


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
    if a.cmd == "cycle" and not a.fixtures:
        # every result of this and last season, for the form checks (daily; the research corpus lags)
        leagues = [d for d in live.LEAGUE_NAMES if d not in live.NO_PRIMARY and d != "MANUAL"]
        form.refresh_recent(now, live.fetch_csv, leagues, a.ledger / "recent_results.csv")
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
