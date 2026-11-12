import pytest

from astrofoot import teamday


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Never touch the real data/ref/team_founding_days.json."""
    monkeypatch.setattr(teamday, "CACHE", tmp_path / "founding_days.json")
    monkeypatch.setattr(teamday, "_mem", None)


def test_team_day_reading_and_pick_filter(monkeypatch):
    monkeypatch.setattr(teamday, "_mem", {"Alpha": {"date": "1899-05-01", "name": "Alpha FC"},
                                          "Beta": {"date": "1902-11-20", "name": "Beta FC"}, "Gamma": None})
    td = teamday.reading("Alpha", "Beta", "2026-11-14T15:00:00+00:00", 51.5, -0.12, resolve=False)
    assert td["day"] == "2026-11-14" and td["home"]["founded"] == "1899-05-01"
    for side in ("home", "away"):
        assert td[side]["score_astro"] in (-1, 0, 1) and td[side]["score_num"] in (-1, 0, 1)
        assert td[side]["num"]["numbers"]["life_path"] >= 1
    assert td["favours"]["astro"] in (0, 1, 2)
    none = teamday.reading("Alpha", "Gamma", "2026-11-14T15:00:00+00:00", None, None, resolve=False)
    assert none["away"]["founded"] is None and none["away"]["score_astro"] == 0 and none["favours"]["astro"] == 0
    # the pick filter on Top picks
    from astrofoot.web import app as web
    p = {"td": td, "ts_pick": "home", "pick": "fav", "fav_is_home": True}
    want = "astro"
    expect = td["home"]["score_astro"] == 1
    assert web._dayfav_ok(p, "score", want) == expect
    assert web._dayfav_ok(p, "result", "astro") == (td["favours"]["astro"] == 1)
    assert web._dayfav_ok({**p, "pick": "draw"}, "result", "astro") is False and web._dayfav_ok(p, "goals", "")


def test_day_reading_on_games_analysed_by_hand(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot.web import app as web

    monkeypatch.setattr(teamday, "_mem", {"Arsenal": {"date": "1886-12-01", "name": "Arsenal F.C."}, "Tottenham": None})
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    client = TestClient(web.app)
    form = {"team_a": "Arsenal", "team_b": "Tottenham", "kickoff_utc": "2030-03-02T15:00", "time_precision": "exact",
            "venue": "London", "lat": "51.555", "lon": "-0.108", "home_side": "A", "context": "league",
            "odds_a": "1.8", "odds_d": "3.6", "odds_b": "4.4", "odds_source": "test", "odds_type": "closing"}
    r = client.post("/analyze", data=form, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    html = client.get(r.headers["location"]).text
    assert "Day reading: astrology and numerology" in html and "Founded 1886-12-01" in html
    # Tottenham is not in the (stubbed) founding table: shown without a reading
    assert "No founding date known to the day" in html
    # a founding date given on Analyze is used for that team
    rec = dict(db.list_matches(db.connect(path))[0])
    rec["founding_json"] = '{"founding_b": {"founded_date": "1882-09-05"}}'
    td = web._manual_teamday(rec)
    assert td["away"]["founded"] == "1882-09-05" and td["home"]["founded"] == "1886-12-01"


def test_soccer_day_filter():
    from astrofoot.web import app as web
    td = lambda a, n, sa=0, sn=0: {"favours": {"astro": a, "num": n},  # noqa: E731
                                   "home": {"score_astro": sa, "score_num": sn}, "away": {"score_astro": 0, "score_num": 0}}
    assert web._soc_day_ok(td(1, 1), "same") and not web._soc_day_ok(td(1, 2), "same") and not web._soc_day_ok(td(0, 0), "same")
    assert web._soc_day_ok(td(2, 0), "astro") and web._soc_day_ok(td(0, 1), "num") and not web._soc_day_ok(td(0, 0), "num")
    assert web._soc_day_ok(td(0, 0, 1, 1), "score") and not web._soc_day_ok(td(0, 0, 1, 0), "score")
    assert web._soc_day_ok(None, "") and not web._soc_day_ok(None, "same")


def test_summary_pick_day_filter():
    from astrofoot.web import app as web
    td = {"favours": {"astro": 1, "num": 1}, "home": {"score_astro": 1, "score_num": 0},
          "away": {"score_astro": 0, "score_num": 0}}
    win = {"td": td, "sum_market": "result", "pick": "fav", "fav_is_home": True}
    dc_away = {"td": td, "sum_market": "dc", "dc_pick": "X2"}
    score_home = {"td": td, "sum_market": "score", "ts_pick": "home"}
    goals = {"td": td, "sum_market": "goals"}
    assert web._dayfav_ok(win, "summary", "both") and not web._dayfav_ok(dc_away, "summary", "astro")
    assert web._dayfav_ok(score_home, "summary", "astro") and not web._dayfav_ok(score_home, "summary", "num")
    assert not web._dayfav_ok(goals, "summary", "astro") and web._dayfav_ok(goals, "summary", "same")


def test_women_teams_never_get_the_mens_founding_date(monkeypatch):
    monkeypatch.setattr(teamday, "_mem", {"Chelsea": {"date": "1905-03-10", "name": "Chelsea F.C."},
                                          "W:Chelsea": None, "W:Arsenal": {"date": "1987-01-01", "name": "Arsenal W.F.C."}})
    td = teamday.reading("Chelsea", "Arsenal", "2026-11-15T13:00:00+00:00", 51.48, -0.19, resolve=False, women=True)
    assert td["home"]["founded"] is None and td["away"]["founded"] == "1987-01-01" and td["women"]
    men = teamday.reading("Chelsea", "Arsenal", "2026-11-15T13:00:00+00:00", 51.48, -0.19, resolve=False)
    assert men["home"]["founded"] == "1905-03-10"
    from astrofoot.web import app as web
    r = {"home": "Chelsea", "away": "Arsenal", "kickoff_utc": "2026-11-15T13:00:00+00:00", "division": "W:eng.w.1"}
    assert web._teamday(r)["women"] and web._teamday({**r, "division": "E0"})["women"] is False
