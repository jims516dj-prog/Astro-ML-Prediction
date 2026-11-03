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
