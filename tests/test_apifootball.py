from datetime import datetime, timezone

from astrofoot import fixtures_apifootball as af
from astrofoot import live

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


def game(fid, h, a, league="Friendlies Clubs", country="World", lid=667, status="NS", t="2026-11-12T18:00:00+00:00",
         venue=None, ft=None):
    return {"fixture": {"id": fid, "date": t, "status": {"short": status}, "venue": venue or {"name": None, "city": None}},
            "league": {"id": lid, "name": league, "country": country}, "teams": {"home": {"name": h}, "away": {"name": a}},
            "score": {"fulltime": {"home": ft[0], "away": ft[1]} if ft else {"home": None, "away": None}}}


def odds_entry(fid, books):
    return {"fixture": {"id": fid}, "bookmakers": [
        {"name": n, "bets": [{"name": "Match Winner", "values": [{"value": "Home", "odd": str(h)}, {"value": "Draw", "odd": str(d)},
                                                                 {"value": "Away", "odd": str(a)}]},
                             {"name": "Goals Over/Under", "values": [{"value": "Over 2.5", "odd": "1.9"},
                                                                     {"value": "Under 2.5", "odd": "1.9"}]}]}
        for n, (h, d, a) in books.items()]}


class Fake(af.Client):
    def __init__(self, fixtures, odds, used=0):
        super().__init__("k")
        self.fixtures, self.odds, self.used_today, self.paths = fixtures, odds, used, []

    def _get(self, q):
        self.paths.append(q)
        if q.startswith("fixtures"):
            day = q.split("date=")[1][:10]
            return {"errors": [], "response": [f for f in self.fixtures if f["fixture"]["date"][:10] == day]}
        if q.startswith("odds"):
            day = q.split("date=")[1][:10]
            rows = [o for o in self.odds if any(f["fixture"]["id"] == o["fixture"]["id"] and f["fixture"]["date"][:10] == day
                                                for f in self.fixtures)]
            return {"errors": [], "paging": {"current": 1, "total": 1}, "response": rows}
        raise AssertionError(q)


def test_prices_pinnacle_else_median():
    got = af.prices(odds_entry(1, {"A": (2.0, 3.4, 3.8), "B": (2.2, 3.2, 3.4)}))
    assert got[0] == [2.1, 3.3, 3.6] and "median of 2" in got[1] and abs(got[2] - 0.5) < 1e-9
    assert af.prices(odds_entry(1, {"A": (2.0, 3.4, 3.8), "Pinnacle": (1.9, 3.5, 4.2)}))[0] == [1.9, 3.5, 4.2]


def test_extra_fixtures_men_women_dedupe_and_shared_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(af, "FILE", tmp_path / "l.json")
    fixtures = [game(1, "Denmark U21", "Netherlands U21", "UEFA U21 Championship - Qualification", lid=38,
                     venue={"name": "Vejle Stadion", "city": "Vejle"}),
                game(2, "Peru", "Bolivia", "Friendlies", lid=10),
                game(3, "Spain W", "Italy W", "Friendlies Women", lid=666),
                game(4, "Club A", "Club B", "Segunda Division", country="El-Salvador", lid=99),
                game(5, "Played", "Before", status="FT")]
    odds = [odds_entry(i, {"Pinnacle": (2.0, 3.3, 3.9)}) for i in (1, 2, 3, 4, 5)]
    c = Fake(fixtures, odds)
    primary = [{"match_key": "x", "division": "X:fifa.friendly", "home": "Peru", "away": "Bolivia",
                "kickoff_utc": "2026-11-12T18:00:00+00:00"}]
    own = lambda team, division=None, hint=None: (55.7, 9.5, "vejle") if hint and hint.get("city") == "Vejle" else None  # noqa: E731
    men = af.extra_fixtures(primary, NOW, 4, live.match_key, lambda k: k[:10], [], own, c=c, log=lambda *a: None,
                            same_game=live.same_game)
    assert [(g["home"], g["division"]) for g in men] == [("Denmark U21", "A:38"), ("Club A", "A:99")]
    assert men[0]["venue_source"] == "vejle" and "San Salvador" in men[1]["venue_source"]
    assert men[0]["odds_source"].endswith("Pinnacle") and men[0]["p_over25"] == 0.5
    n = c.calls
    women = af.extra_fixtures([], NOW, 4, live.match_key, lambda k: k[:10], [], own, c=c, log=lambda *a: None, women=True)
    assert [(g["home"], g["division"]) for g in women] == [("Spain W", "W:a666")] and c.calls == n   # answers reused
    assert af.league_name("A:38") == "World: UEFA U21 Championship - Qualification"


def test_budget_stops_at_daily_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(af, "FILE", tmp_path / "l.json")
    c = Fake([], [], used=af.DAY_LIMIT)
    logs = []
    assert af.extra_fixtures([], NOW, 4, live.match_key, lambda k: k[:10], [], None, c=c, log=logs.append) == []
    assert c.paths == [] and c.calls == 0


def test_results_use_90_minute_score():
    fixtures = [game(1, "Denmark U21", "Netherlands U21", status="AET", t="2026-11-11T18:00:00+00:00", ft=(1, 1)),
                game(2, "X", "Y", status="NS", t="2026-11-11T20:00:00+00:00")]
    c = Fake(fixtures, [])
    pending = [{"match_key": "k1", "division": "A:38", "home": "Denmark U21", "away": "Netherlands U21",
                "kickoff_utc": "2026-11-11T18:00:00+00:00"}]
    got = af.match_results(pending, c=c, log=lambda *a: None)
    assert got["k1"]["goals_home"] == 1 and got["k1"]["goals_away"] == 1
