from astrofoot import teamday


def test_team_day_reading_and_pick_filter(monkeypatch):
    monkeypatch.setattr(teamday, "_load", lambda: {"Alpha": {"date": "1899-05-01", "name": "Alpha FC"},
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
