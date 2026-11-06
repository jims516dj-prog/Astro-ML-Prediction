from astrofoot import db, mypicks

from test_merged import live_rec


def test_outcomes_cover_every_market_and_sum_sensibly():
    r = live_rec("K", "Alpha", "Beta", "2026-11-09T15:00:00+00:00")
    opts = mypicks.options(r)
    codes = {o["code"] for o in opts}
    assert {"result:home", "result:draw", "result:away", "dc:1X", "o15:over", "hs:yes", "as:no", "btts:yes"} <= codes
    assert [o["p"] for o in opts] == sorted((o["p"] for o in opts), reverse=True)
    p = {o["code"]: o["p"] for o in opts}
    assert abs(p["result:home"] + p["result:draw"] + p["result:away"] - 1) < 1e-9
    assert abs(p["btts:yes"] + p["btts:no"] - 1) < 1e-9


def test_won_rules():
    assert mypicks.won("result:home", 2, 1) and not mypicks.won("result:draw", 2, 1)
    assert mypicks.won("dc:X2", 1, 1) and not mypicks.won("dc:12", 0, 0)
    assert mypicks.won("o15:over", 1, 1) and mypicks.won("o25:under", 1, 1)
    assert mypicks.won("hs:no", 0, 3) and mypicks.won("as:yes", 0, 3)
    assert mypicks.won("btts:no", 0, 3) and mypicks.won("btts:yes", 1, 1)


def test_score_ignores_late_and_unsettled_and_all_win():
    picks = [{"p": 0.8, "hit": True, "late": False}, {"p": 0.6, "hit": False, "late": False},
             {"p": 0.9, "hit": True, "late": True}, {"p": 0.7, "hit": None, "late": False}]
    s = mypicks.score(picks)
    assert s["n"] == 2 and s["hits"] == 1 and abs(s["expected"] - 0.7) < 1e-9
    assert abs(mypicks.all_win(picks) - 0.8 * 0.6 * 0.9 * 0.7) < 1e-12


def test_saving_replaces_the_days_picks(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    base = {"kickoff_utc": "2026-11-09T15:00:00+00:00", "home": "A", "away": "B", "label": "A win", "p": 0.5,
            "picked_at": "2026-11-08T10:00:00+00:00"}
    db.save_my_picks(c, "2026-11-09", [{**base, "match_key": "k1", "selection": "result:home"},
                                       {**base, "match_key": "k2", "selection": "btts:yes"}])
    db.save_my_picks(c, "2026-11-10", [{**base, "match_key": "k3", "selection": "o15:over"}])
    db.save_my_picks(c, "2026-11-09", [{**base, "match_key": "k2", "selection": "btts:no"}])
    assert [(p["match_key"], p["selection"]) for p in db.my_picks(c, "2026-11-09")] == [("k2", "btts:no")]
    assert len(db.my_picks(c)) == 2
