"""Founding dates you enter: used for the day reading of every game of that team, ahead of the founding table."""


def test_entered_founding_date_is_used_and_removable(tmp_path, monkeypatch):
    from astrofoot import config, db, teamday
    path = tmp_path / "app.sqlite3"
    monkeypatch.setattr(config, "DB_PATH", path)
    c = db.connect(path)
    monkeypatch.setattr(db, "connect", lambda p=path: _con(path))
    teamday.reload_user_dates()
    assert teamday.founding("Nowhere United", resolve=False) is None
    db.save_team_chart(c, "Nowhere United", "1911-04-03", None, None, None, None, based_on="test")
    db.save_team_chart(c, "W:Nowhere United", "1990-06-01", None, None, None, None, based_on="test")
    teamday.reload_user_dates()
    assert teamday.founding("Nowhere United", resolve=False) == {"date": "1911-04-03", "name": "Nowhere United",
                                                                  "source": "you"}
    assert teamday.founding("Nowhere United", resolve=False, women=True)["date"] == "1990-06-01"
    r = teamday.reading("Nowhere United", "Elsewhere", "2026-11-14T15:00:00Z", resolve=False)
    assert r["home"]["founded"] == "1911-04-03" and r["home"]["founded_by"] == "you"
    assert r["home"]["astro"]["score"] is not None
    db.delete_team_chart(c, "Nowhere United")
    teamday.reload_user_dates()
    assert teamday.founding("Nowhere United", resolve=False) is None
    teamday.reload_user_dates()


def _con(path):
    import sqlite3
    from astrofoot import db
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c
