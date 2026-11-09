import json
from datetime import datetime, timezone

import pandas as pd

from astrofoot import fixtures2, live

NOW = datetime(2026, 11, 3, 11, 17, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, events, odds, remaining=400):
        self.events, self.odds, self.remaining, self.calls = events, odds, remaining, []

    def get(self, path, **params):
        self.calls.append(path)
        if path == "/sports":
            return [{"key": k, "active": True} for k in self.events]
        sport = path.split("/")[2]
        if path.endswith("/events"):
            return self.events[sport]
        self.remaining -= 1
        return self.odds[sport]


def ev(i, home, away, ko):
    return {"id": i, "home_team": home, "away_team": away, "commence_time": ko}


def priced(i, home, away, books):
    return {"id": i, "bookmakers": [{"key": k, "markets": [{"key": "h2h", "outcomes": [
        {"name": home, "price": h}, {"name": "Draw", "price": d}, {"name": away, "price": a}]}]}
        for k, (h, d, a) in books.items()]}


def results_csv(_url):
    return pd.DataFrame({"Date": ["25/10/2026", "26/10/2026"], "HomeTeam": ["Man United", "Nott'm Forest"],
                         "AwayTeam": ["Wolves", "Newcastle"], "FTHG": [1, 2], "FTAG": [0, 2]})


def local_date(ko):
    return pd.Timestamp(ko).tz_convert("Europe/London").strftime("%Y-%m-%d")


def run(client, tmp_path, primary=(), preds=()):
    return fixtures2.extra_fixtures(list(primary), NOW, 4, tmp_path, client, results_csv, live.results_url,
                                    live.match_key, local_date, list(preds), log=lambda *a: None)


def test_adds_unlisted_game_with_canonical_names_and_same_key(tmp_path):
    c = FakeClient(
        {"soccer_epl": [ev("x", "Manchester United", "Wolverhampton Wanderers", "2026-11-04T15:00:00Z"),
                        ev("far", "Nottingham Forest", "Newcastle United", "2026-11-06T20:00:00Z")]},
        {"soccer_epl": [priced("x", "Manchester United", "Wolverhampton Wanderers",
                               {"pinnacle": (1.8, 3.8, 4.6), "unibet": (1.7, 3.6, 4.4)})]})
    out = run(c, tmp_path)
    assert len(out) == 1                                   # the far game is not bought yet
    f = out[0]
    assert (f["home"], f["away"], f["division"]) == ("Man United", "Wolves", "E0")
    assert f["match_key"] == live.match_key("E0", "2026-11-04", "Man United", "Wolves")
    assert abs(f["odds"]["home"] - 1.75) < 1e-9 and "average of 2" in f["odds_source"]
    # bought once; a second cycle within 20 h does not spend another credit
    assert json.loads((tmp_path / "odds_api_state.json").read_text())["soccer_epl"]
    c.calls.clear()
    run(c, tmp_path)
    assert not any(p.endswith("/odds") for p in c.calls)


def test_skips_games_the_primary_lists_or_already_forecast_and_unknown_names(tmp_path):
    c = FakeClient(
        {"soccer_epl": [ev("x", "Manchester United", "Wolves", "2026-11-04T15:00:00Z"),
                        ev("y", "Nottingham Forest", "Newcastle", "2026-11-04T19:45:00Z"),
                        ev("z", "Real Madrid", "Barcelona", "2026-11-04T19:45:00Z")]},
        {"soccer_epl": []})
    primary = [{"match_key": "k1", "division": "E0", "home": "Man United", "away": "Wolves",
                "kickoff_utc": "2026-11-04T15:00:00+00:00"}]
    preds = [{"match_key": live.match_key("E0", "2026-11-04", "Nott'm Forest", "Newcastle"), "division": "E0",
              "home": "Nott'm Forest", "away": "Newcastle"}]
    out = run(c, tmp_path, primary, preds)
    assert out == [] and not any(p.endswith("/odds") for p in c.calls)


def test_bet365_preferred_and_credit_floor(tmp_path):
    e = {"soccer_epl": [ev("x", "Manchester United", "Wolves", "2026-11-04T15:00:00Z")]}
    o = {"soccer_epl": [priced("x", "Manchester United", "Wolves", {"bet365": (1.9, 3.5, 4.0), "pinnacle": (2, 3, 4)})]}
    out = run(FakeClient(e, o), tmp_path)
    assert out[0]["odds"] == {"home": 1.9, "draw": 3.5, "away": 4.0} and out[0]["odds_source"].endswith("Bet365")
    low = FakeClient(e, o, remaining=3)
    assert run(low, tmp_path / "other") == []


def test_canonical_name_refuses_ambiguity():
    known = {"Man United", "Man City", "Wolves"}
    assert fixtures2.canonical_name("Manchester City", known) == "Man City"
    assert fixtures2.canonical_name("Manchester", known) is None


def test_european_fixtures_names_grounds_and_totals(tmp_path):
    e = {"soccer_uefa_champs_league": [ev("u1", "Manchester United", "Slavia Praha", "2026-11-04T15:00:00Z"),
                                       ev("u2", "Qarabag FK", "Wolverhampton Wanderers", "2026-11-04T15:00:00Z")]}
    book = lambda i, h, a: {"id": i, "bookmakers": [{"key": "pinnacle", "markets": [
        {"key": "h2h", "outcomes": [{"name": h, "price": 1.5}, {"name": "Draw", "price": 4.4}, {"name": a, "price": 6.5}]},
        {"key": "totals", "outcomes": [{"name": "Over", "price": 1.8, "point": 2.5}, {"name": "Under", "price": 2.05, "point": 2.5}]}]}]}
    o = {"soccer_uefa_champs_league": [book("u1", "Manchester United", "Slavia Praha"),
                                       book("u2", "Qarabag FK", "Wolverhampton Wanderers")]}
    c = FakeClient(e, o)
    grounds = {"Man United": (53.46, -2.29, "stadium")}
    out = fixtures2.extra_fixtures([], NOW, 4, tmp_path, c, results_csv, live.results_url, live.match_key, local_date, [],
                                   log=lambda *a: None, venue_of=lambda t, **kw: grounds.get(t),
                                   european_pool={"Man United", "Wolves", "Nott'm Forest"})
    assert len(out) == 1                                    # Qarabag's ground unknown here: skipped, not guessed
    f = out[0]
    assert (f["division"], f["home"], f["away"]) == ("UCL", "Man United", "Slavia Praha")
    assert f["venue_lat"] == 53.46 and abs(f["p_over25"] - (1 / 1.8) / (1 / 1.8 + 1 / 2.05)) < 1e-9


def test_european_results_settle_without_primary_and_void_after_three_days(tmp_path):
    from datetime import timedelta
    from astrofoot import results_espn
    rec = {"match_key": "eu1", "division": "UCL", "home": "Man United", "away": "Slavia Praha",
           "kickoff_utc": "2026-11-04T20:00:00+00:00"}
    other = {**rec, "match_key": "eu2", "home": "Inter", "away": "Club Brugge"}
    (tmp_path / "predictions").mkdir()
    (tmp_path / "predictions" / "x.jsonl").write_text("\n".join(json.dumps(r) for r in (rec, other)) + "\n")
    assert live.needed_result_urls(tmp_path, NOW + timedelta(days=1)) == set()
    aet = {"date": "2026-11-04T20:00Z", "status": {"type": {"name": "STATUS_FINAL_AET", "completed": True}},
           "competitions": [{"date": "2026-11-04T20:00Z", "competitors": [
               {"homeAway": "home", "score": "3", "team": {"displayName": "Manchester United"},
                "linescores": [{"value": 1}, {"value": 1}, {"value": 1}]},
               {"homeAway": "away", "score": "2", "team": {"displayName": "Slavia Prague"},
                "linescores": [{"value": 0}, {"value": 2}, {"value": 0}]}]}]}
    found, _, _ = results_espn.match_results([rec], fetcher=lambda *a: [aet])
    assert found["eu1"]["goals_home"] == 2 and found["eu1"]["goals_away"] == 2     # 90 minutes, not 120
    n = live.settle(found, NOW + timedelta(days=1), tmp_path)
    assert n == 1                                                                   # eu2 not void yet
    n = live.settle({}, NOW + timedelta(days=5), tmp_path)
    res = live.read_results(tmp_path)
    assert n == 1 and res["eu2"]["void"] and not res["eu1"].get("void")


def test_european_game_not_forecast_twice_under_another_spelling(tmp_path):
    e = {"soccer_uefa_europa_league": [ev("x", "Bayer Leverkusen", "Marseille", "2026-11-04T15:00:00Z")]}
    o = {"soccer_uefa_europa_league": [priced("x", "Bayer Leverkusen", "Marseille", {"pinnacle": (1.7, 4.0, 4.5)})]}
    earlier = [{"match_key": "old", "division": "UEL", "home": "Leverkusen", "away": "Marseille",
                "kickoff_utc": "2026-11-04T15:00:00+00:00"}]
    run = lambda preds: fixtures2.extra_fixtures([], NOW, 4, tmp_path, FakeClient(e, o), results_csv, live.results_url,
                                                 live.match_key, local_date, preds, log=lambda *a: None,
                                                 venue_of=lambda t, **kw: (51.0, 7.0, "x"), european_pool=set())
    assert run(earlier) == []
    assert len(run([])) == 1
