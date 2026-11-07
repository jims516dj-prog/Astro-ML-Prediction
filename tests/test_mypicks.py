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


def test_slips_hold_picks_once_per_game_and_a_game_can_be_on_several(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    base = {"kickoff_utc": "2026-11-09T15:00:00+00:00", "home": "A", "away": "B", "label": "A win", "p": 0.5,
            "picked_at": "2026-11-08T10:00:00+00:00"}
    s1, s2 = db.create_slip(c, "2026-11-09"), db.create_slip(c, "2026-11-09")
    assert [x["name"] for x in db.slips(c, "2026-11-09")] == ["Slip 1", "Slip 2"]
    assert db.add_pick(c, s1, "2026-11-09", {**base, "match_key": "k1", "selection": "result:home"})
    assert not db.add_pick(c, s1, "2026-11-09", {**base, "match_key": "k1", "selection": "btts:yes"})   # once per slip
    assert db.add_pick(c, s2, "2026-11-09", {**base, "match_key": "k1", "selection": "btts:yes"})       # other slip: fine
    assert [(p["slip_name"], p["selection"]) for p in db.my_picks(c, "2026-11-09")] == [("Slip 1", "result:home"),
                                                                                       ("Slip 2", "btts:yes")]
    db.rename_slip(c, s2, "Goals slip")
    db.delete_slip(c, s1)
    assert [(x["name"], x["n"]) for x in db.slips(c)] == [("Goals slip", 1)]
    assert db.create_slip(c, "2026-11-09") and db.slips(c)[-1]["name"] == "Slip 1"         # first free number


def test_old_picks_move_into_slip_1(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite3"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE my_picks (match_key TEXT PRIMARY KEY, day TEXT NOT NULL, kickoff_utc TEXT NOT NULL, home TEXT "
                "NOT NULL, away TEXT NOT NULL, league TEXT, selection TEXT NOT NULL, label TEXT NOT NULL, p REAL, "
                "picked_at TEXT NOT NULL, url TEXT)")
    for k, d in (("k1", "2026-11-01"), ("k2", "2026-11-01"), ("k3", "2026-11-02")):
        old.execute("INSERT INTO my_picks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (k, d, d + "T15:00:00+00:00", "A", "B", "E0", "result:home", "A win", 0.5, d + "T09:00:00+00:00", None))
    old.commit()
    old.close()
    c = db.connect(path)
    assert [(x["day"], x["name"], x["n"]) for x in db.slips(c)] == [("2026-11-01", "Slip 1", 2), ("2026-11-02", "Slip 1", 1)]
    assert c.execute("SELECT COUNT(*) FROM my_picks_v1_backup").fetchone()[0] == 3
    assert len(db.my_picks(db.connect(path))) == 3                                       # migration runs once


def test_slip_result():
    from astrofoot.web.app import _slip_summary
    pk = lambda hit, status="settled", late=False: {"hit": hit, "status": status, "late": late, "p": 0.8}   # noqa: E731
    assert _slip_summary([pk(True), pk(True)])["state"] == "won"
    assert _slip_summary([pk(True), pk(None, "pending")])["state"] == "open"
    assert _slip_summary([pk(False), pk(None, "pending")])["state"] == "lost"
    assert _slip_summary([pk(True), pk(None, "void")])["state"] == "won"
    assert _slip_summary([])["state"] == "empty"


def test_astrology_agrees_with_the_chosen_outcome():
    scores = {"rao": (2, 1), "chokoisky": (1, 1), "frawley": None}       # home first; Frawley disabled
    assert mypicks.agree("result:home", scores) == (1, 2)
    assert mypicks.agree("dc:1X", scores) == (2, 2)
    assert mypicks.agree("btts:yes", scores) == (2, 2)
    assert mypicks.agree("o25:over", scores) == (1, 2)
    assert mypicks.agree("as:no", scores) == (0, 2)


def test_edit_changes_or_removes_by_pick(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    base = {"kickoff_utc": "2026-11-09T15:00:00+00:00", "home": "A", "away": "B", "label": "x", "p": 0.5,
            "picked_at": "2026-11-08T10:00:00+00:00"}
    sid = db.create_slip(c, "2026-11-09")
    db.add_pick(c, sid, "2026-11-09", {**base, "match_key": "k1", "selection": "result:home"})
    db.add_pick(c, sid, "2026-11-09", {**base, "match_key": "k2", "selection": "btts:yes"})
    p1, p2 = db.my_picks(c, slip_id=sid)
    db.update_pick(c, p1["id"], "result:draw", "Draw", 0.3, "2026-11-08T11:00:00+00:00")
    db.delete_pick(c, p2["id"])
    assert [(p["match_key"], p["selection"]) for p in db.my_picks(c, "2026-11-09")] == [("k1", "result:draw")]


def test_report_and_csv_show_every_pick_in_full(tmp_path, monkeypatch):
    import csv
    import io

    from fastapi.testclient import TestClient

    from astrofoot.web import app as web
    from test_merged import live_rec

    g = live_rec("K1", "Alpha", "Beta", "2026-11-09T15:00:00+00:00")
    g.update(sha256="ab" * 32, odds={"home": 1.8, "draw": 3.6, "away": 4.4}, odds_source="test book",
             venue_lat=None, venue_lon=None, ts_engine_scores={"rao": (2, 1), "chokoisky": (1, 0), "frawley": None})
    path = tmp_path / "t.sqlite3"
    c = db.connect(path)
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    monkeypatch.setattr(web, "_all_games", lambda include_withdrawn=False: [g])
    db.add_pick(c, db.create_slip(c, "2026-11-09", "Main slip"), "2026-11-09", {"match_key": "K1", "kickoff_utc": g["kickoff_utc"], "home": "Alpha",
                                        "away": "Beta", "selection": "o15:over", "label": "Over 1.5 goals", "p": 0.74,
                                        "picked_at": "2026-11-09T09:00:00+00:00", "url": g["url"]})
    client = TestClient(web.app)
    html = client.get("/mypicks/report?day=2026-11-09").text
    for text in ("Alpha v Beta", "Over 1.5 goals", "74.0%", "test book", "abababab", "2–1", "Method and caveats", "Main slip"):
        assert text in html, text
    rows = list(csv.DictReader(io.StringIO(client.get("/mypicks/export.csv?day=2026-11-09").text)))
    assert len(rows) == 1 and rows[0]["slip"] == "Main slip" and rows[0]["pick"] == "Over 1.5 goals" and rows[0]["rao_predicted_score_home_first"] == "2-1"
    assert rows[0]["rao_agrees"] == "yes" and rows[0]["astrology_agrees"] == "1" and rows[0]["engines_with_score"] == "2" and rows[0]["picked_after_kickoff"] == "no"


def test_day_labels():
    from datetime import datetime, timedelta, timezone

    from astrofoot.web.app import _day_label
    today = datetime.now(timezone.utc).date()
    assert _day_label(today.isoformat()) == "Today"
    assert _day_label((today - timedelta(days=1)).isoformat()) == "Yesterday"
    assert _day_label((today + timedelta(days=1)).isoformat()) == "Tomorrow"
    other = (today - timedelta(days=5)).isoformat()
    assert _day_label(other) == other and _day_label("not a date") == "not a date"


def test_my_picks_expected_goals_filter(tmp_path, monkeypatch):
    import re

    from fastapi.testclient import TestClient

    from astrofoot.web import app as web
    from test_merged import live_rec
    strong = live_rec("S1", "Strong", "Weak", "2026-11-09T15:00:00+00:00")
    strong["predictions"]["market"] = {"fav": 0.75, "draw": 0.15, "dog": 0.10}
    even = live_rec("S2", "Even", "Match", "2026-11-09T17:00:00+00:00")
    even["predictions"]["market"] = {"fav": 0.38, "draw": 0.30, "dog": 0.32}
    path = tmp_path / "t.sqlite3"
    db.connect(path)
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    monkeypatch.setattr(web, "_all_games", lambda include_withdrawn=False: [strong, even])
    c = TestClient(web.app)
    games = lambda q: re.findall(r'name="game" value="([^"]+)"', c.get("/mypicks?day=2026-11-09" + q).text)   # noqa: E731
    assert games("") == ["S1", "S2"]
    assert games("&xg=1.5") == ["S1"] and games("&xg=1.5&xg_for=home") == ["S1"] and games("&xg=1.5&xg_for=away") == []
    assert games("&xg=1.5&xg_for=backed") == ["S1"]          # live_rec: all three engines back the favourite
    assert games("&xg=nonsense") == ["S1", "S2"]
