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
