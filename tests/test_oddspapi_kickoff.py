from datetime import datetime, timezone

from astrofoot import fixtures_oddspapi as op
from astrofoot import live, results_kickoff as rk

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


def book(h, d, a, over=None, under=None):
    p = lambda x: {"players": {"0": {"price": x}}}  # noqa: E731
    m = {"101": {"outcomes": {"101": p(h), "102": p(d), "103": p(a)}}}
    if over:
        m["1010"] = {"outcomes": {"1010": p(over), "1011": p(under)}}
    return {"markets": m}


class Fake:
    def __init__(self, fixtures, odds):
        self.fixtures, self.odds, self.calls = fixtures, odds, 0

    def get(self, path, **kw):
        self.calls += 1
        if path == "/fixtures":
            return self.fixtures
        tids = kw["tournamentIds"].split(",")
        return [{"fixtureId": f["fixtureId"], **self.odds[f["fixtureId"]]} for f in self.fixtures
                if str(f["tournamentId"]) in tids]


def fx(fid, h, a, t="2026-11-12T18:00:00.000Z", cat="International Youth", tour="U21 Friendly Games", status="Pre-Game",
       tid=77):
    return {"fixtureId": fid, "participant1Name": h, "participant2Name": a, "startTime": t, "statusName": status,
            "tournamentId": tid, "tournamentName": tour, "categoryName": cat, "hasOdds": True}


def test_prices_prefer_pinnacle_else_median():
    got = op.prices({"bookmakerOdds": {"a": book(2.0, 3.4, 3.8), "b": book(2.2, 3.2, 3.4, 1.9, 1.9)}})
    assert got[0] == [2.1, 3.3, 3.6] and "median of 2" in got[1] and abs(got[2] - 0.5) < 1e-9
    got = op.prices({"bookmakerOdds": {"a": book(2.0, 3.4, 3.8), "pinnacle": book(1.9, 3.5, 4.2)}})
    assert got[0] == [1.9, 3.5, 4.2] and got[1].endswith("Pinnacle")
    assert op.prices({"bookmakerOdds": {"a": {"markets": {}}}}) is None


def test_extra_fixtures_filters_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "FILE", tmp_path / "t.json")
    monkeypatch.setattr(op, "USAGE", tmp_path / "u.json")
    monkeypatch.setattr(op, "_FX", {})
    monkeypatch.setattr(op.time, "sleep", lambda s: None)
    fixtures = [fx("f1", "Denmark U21", "Netherlands U21"),
                fx("f2", "SRL Arsenal", "SRL Chelsea", cat="Simulated Reality League", tour="Premier League SRL"),
                fx("f3", "Spain Women", "Italy Women", tour="Women Friendlies", tid=88),
                fx("f4", "Peru", "Bolivia", cat="International", tour="Int. Friendly Games", tid=99),
                fx("f5", "Old", "Game", status="Finished")]
    odds = {f["fixtureId"]: {"bookmakerOdds": {"pinnacle": book(2.0, 3.3, 3.9)}} for f in fixtures}
    primary = [{"match_key": "x", "division": "X:fifa.friendly", "home": "Peru", "away": "Bolivia",
                "kickoff_utc": "2026-11-12T18:00:00+00:00"}]
    local = lambda ko: ko[:10]  # noqa: E731
    got = op.extra_fixtures(primary, NOW, 2, live.match_key, local, [], lambda t, **kw: (55.7, 12.6, "test"),
                            client=Fake(fixtures, odds), log=lambda *a: None, same_game=live.same_game)
    assert [(g["home"], g["division"]) for g in got] == [("Denmark U21", "O:77")]
    assert got[0]["odds"] == {"home": 2.0, "draw": 3.3, "away": 3.9} and got[0]["league"] == "International Youth: U21 Friendly Games"
    women = op.extra_fixtures([], NOW, 2, live.match_key, local, [], lambda t, **kw: (41.9, 12.5, "test"),
                              client=Fake(fixtures, odds), log=lambda *a: None, women=True)
    assert [(g["home"], g["division"]) for g in women] == [("Spain Women", "W:o88")]
    assert op.league_name("O:77") == "International Youth: U21 Friendly Games"


def test_kickoff_results_pair_and_skip_extra_time():
    rows = [{"date": "2026-11-12T18:00:00Z", "status": {"short": "FT"}, "home": {"name": "Denmark U21"},
             "away": {"name": "Netherlands U21"}, "score": {"home": 2, "away": 1}},
            {"date": "2026-11-12T18:00:00Z", "status": {"short": "PEN"}, "home": {"name": "Peru"},
             "away": {"name": "Bolivia"}, "score": {"home": 1, "away": 1}}]
    pending = [{"match_key": "k1", "division": "O:77", "home": "Denmark U21", "away": "Netherlands U21",
                "kickoff_utc": "2026-11-12T18:00:00+00:00"},
               {"match_key": "k2", "division": "O:78", "home": "Peru", "away": "Bolivia",
                "kickoff_utc": "2026-11-12T18:00:00+00:00"}]
    got = rk.match_results(pending, key="k", fetch=lambda d, k: rows, log=lambda *a: None)
    assert got == {"k1": {"goals_home": 2, "goals_away": 1, "source": "kickoffapi.com"}}


def test_new_divisions_are_secondary():
    from astrofoot import dataset
    assert "O:77" in dataset.NO_PRIMARY and "W:o77" in dataset.NO_PRIMARY


def test_ground_falls_back_to_first_team_then_country_city():
    own = lambda n, **kw: (1.0, 2.0, "g") if n == "Rosario Central" else None  # noqa: E731
    assert op.ground({"categoryName": "Argentina"}, "Rosario Central Reserve", "O:1", own) == (1.0, 2.0, "g (first team's ground)")
    lat, lon, src = op.ground({"categoryName": "Egypt"}, "Tanta FC", "O:1", own)
    assert round(lat) == 30 and "Cairo" in src
    assert "Berlin" in op.ground({"categoryName": "Germany Amateur"}, "X", "O:1", None)[2]
    assert "Belfast" in op.ground({"categoryName": "Northern Ireland"}, "X", "O:1", None)[2]
    assert op.ground({"categoryName": "International Clubs"}, "X", "O:1", None) is None


def test_oddspapi_quota_spread_and_429(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "USAGE", tmp_path / "u.json")
    monkeypatch.setattr(op, "_FX", {})
    u = op.usage("2026-11-12")
    assert op.allowance(u, "2026-11-12") == 240 // 19
    u["used"], u["day_used"] = 100, 5
    assert op.allowance(u, "2026-11-12") == 140 // 19 - 5

    class Busy:
        calls = 0

        def get(self, path, **kw):
            self.calls += 1
            raise RuntimeError("HTTP Error 429: Too Many Requests")
    logs = []
    assert op.extra_fixtures([], NOW, 2, live.match_key, lambda k: k[:10], [], None, client=Busy(), log=logs.append) == []
    assert op.usage("2026-11-13")["blocked"] and op.allowance(op.usage("2026-11-13"), "2026-11-13") == 0
    assert op.usage("2026-12-01").get("blocked") is None          # a new month starts afresh
