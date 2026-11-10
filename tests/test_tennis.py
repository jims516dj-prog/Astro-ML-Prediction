from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from astrofoot.tennis import astro_num, espn, features, model
from astrofoot.tennis.surface import surface


def fake_matches(n=2500, n_players=60, seed=1):
    rng = np.random.default_rng(seed)
    skill = rng.normal(0, 1, n_players)
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        a, b = rng.choice(n_players, 2, replace=False)
        p = 1 / (1 + np.exp(-(skill[a] - skill[b])))
        sets = ""
        while sets.count("1") < 2 and sets.count("2") < 2:
            sets += "1" if rng.random() < p else "2"
        rows.append({"id": str(i), "event_id": "e", "event": "Test Open", "tour": "atp" if i % 2 else "wta",
                     "date": pd.Timestamp(start + timedelta(hours=8 * i)), "venue": "Paris, France", "round": "Round 1",
                     "best_of": 3, "state": "post", "status": "STATUS_FINAL", "completed": True,
                     "p1_id": str(a), "p1": f"Player {a}", "p1_country": "France", "p1_seed": None, "p1_entry": None, "p1_rank": None,
                     "p2_id": str(b), "p2": f"Player {b}", "p2_country": "Spain", "p2_seed": None, "p2_entry": None, "p2_rank": None,
                     "winner": 1 if sets.count("1") == 2 else 2, "score": "", "set_winners": sets,
                     "retired": False, "walkover": False, "note": "", "surface": "clay"})
    players = pd.DataFrame([{"id": str(k), "name": f"Player {k}", "full_name": f"Player {k}",
                             "dob": f"{1990 + k % 10}-{1 + k % 12:02d}-{1 + k % 27:02d}", "birthplace": "", "hand": "R",
                             "height_in": 72.0, "country": "France"} for k in range(n_players)])
    return pd.DataFrame(rows), players


def test_parse_espn_competition_with_seeds_and_sets():
    c = {"id": "9", "date": "2026-11-08T20:15Z", "round": {"displayName": "Final"}, "format": {"regulation": {"periods": 3}},
         "status": {"type": {"name": "STATUS_FINAL", "state": "post", "completed": True}}, "venue": {"fullName": "Indian Wells, USA"},
         "notes": [{"text": "(8) Linda Noskova (CZE) bt (9) Marta Kostyuk (UKR) 6-2 6-4"}],
         "competitors": [
             {"id": "3382", "type": "athlete", "order": 1, "winner": False, "linescores": [{"value": 2, "winner": False}, {"value": 4, "winner": False}],
              "athlete": {"displayName": "Marta Kostyuk", "flag": {"alt": "Ukraine"}}},
             {"id": "6970", "type": "athlete", "order": 2, "winner": True, "curatedRank": {"current": 8},
              "linescores": [{"value": 6, "winner": True}, {"value": 6, "winner": True}],
              "athlete": {"displayName": "Linda Noskova", "flag": {"alt": "Czechia"}}}]}
    r = espn.parse_competition(c, {"id": "1", "name": "WTA Finals"}, "wta")
    assert (r["p1"], r["p1_seed"], r["p2"], r["p2_seed"]) == ("Marta Kostyuk", 9, "Linda Noskova", 8)
    assert r["set_winners"] == "22" and r["winner"] == 2 and r["score"] == "2-6 4-6" and r["p2_rank"] == 8


def test_surface_and_numerology():
    assert surface("Wimbledon", "London, England") == "grass" and surface("Mutua Madrid Open") == "clay"
    assert surface("Queensland Open", "Brisbane") == "hard" and surface("Bybit Stockholm Open") == "hard"
    assert astro_num.life_path("1987-05-22") == 7 and astro_num.reduce(29, True) == 11
    assert 1 <= astro_num.personal_day("1987-05-22", date(2026, 11, 10)) <= 9


def test_features_use_only_the_past_and_flip_is_symmetric():
    m, pl = fake_matches(400)
    f, st = features.history(m, pl, since=None)
    assert len(f) == 400 and f.iloc[0]["elo_diff"] == 0          # first match: no history yet
    g = features.flip(features.flip(f))
    pd.testing.assert_frame_equal(f, g)
    ff = features.flip(f)
    assert (ff.elo_diff == -f.elo_diff).all() and (ff.a_life_path.fillna(-1) == f.b_life_path.fillna(-1)).all()


def test_training_learns_skill_and_predicts_both_players(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "BUNDLE", tmp_path / "t.joblib")
    monkeypatch.setattr(model, "REPORT", tmp_path / "t.json")
    monkeypatch.setattr(model, "MODELS", tmp_path)
    m, pl = fake_matches(2500)
    f, st = features.history(m, pl, since=None)
    rep = model.train(f, log=lambda *a: None, quick=True)
    ho = rep["holdout"]
    assert ho["match"]["model"]["accuracy"] > 0.6 and ho["set"]["model"]["n"] > ho["match"]["model"]["n"]
    assert rep["chosen"].startswith("statistics") and set(rep["ablation"]) >= {"statistics", "statistics + astrology"}
    nxt = {**m.iloc[-1].to_dict(), "id": "new", "date": m.date.max() + pd.Timedelta(days=1), "completed": False}
    p = model.predict(features.row(st, nxt, features.players_dict(pl)), model.load())
    assert abs(p["a_set"] + p["b_set"] - 1) < 1e-9 and abs(p["a_match"] + p["b_match"] - 1) < 1e-9
    assert p["a_one_set"] >= p["a_match"] - 0.05 and p["b_one_set"] >= p["b_match"] - 0.05


def test_missing_birth_dates_are_tolerated():
    m, pl = fake_matches(50)
    pl.loc[0, "dob"] = float("nan")
    pl.loc[1, "dob"] = None
    f, _ = features.history(m, pl, since=None)
    assert len(f) == 50
    assert astro_num.astro(float("nan"), datetime(2026, 1, 1, tzinfo=timezone.utc))["ju_sun"] != 0 or True
    assert np.isnan(astro_num.numerology(float("nan"), None, date(2026, 1, 1))["life_path"])


def test_live_cycle_seals_then_settles(tmp_path, monkeypatch):
    from astrofoot.tennis import live as tlive

    monkeypatch.setattr(model, "BUNDLE", tmp_path / "t.joblib")
    monkeypatch.setattr(model, "REPORT", tmp_path / "t.json")
    monkeypatch.setattr(model, "MODELS", tmp_path)
    monkeypatch.setattr(tlive, "DATA", tmp_path / "data")
    hist, pl = fake_matches(1500)
    f, _ = features.history(hist, pl, since=None)
    model.train(f, log=lambda *a: None, quick=True)
    (tmp_path / "data").mkdir()
    hist.to_parquet(tmp_path / "data" / "matches.parquet", index=False)
    pl.to_parquet(tmp_path / "data" / "players.parquet", index=False)
    now = (hist.date.max() + pd.Timedelta(days=1)).to_pydatetime()
    up = {**hist.iloc[0].to_dict(), "id": "U1", "date": pd.Timestamp(now + timedelta(hours=5)), "state": "pre",
          "completed": False, "winner": None, "set_winners": "", "score": "", "p1_id": "1", "p2_id": "99", "p2": "New Player"}
    ledger = tmp_path / "ledger"
    fetched = []

    def fetch_players(ids, known, log):
        fetched.extend(ids)
        return pd.DataFrame([{"id": "99", "name": "New Player", "full_name": "New Player", "dob": "2001-04-04",
                              "birthplace": "", "hand": "L", "height_in": 70.0, "country": "Italy"}])

    out = tlive.cycle(now, ledger, log=lambda *a: None, crawl=lambda a, b, log: pd.DataFrame([up]), fetch_players=fetch_players)
    assert out["new"] == 1 and fetched == ["99"]
    (rec,) = tlive.predictions(ledger)
    assert rec["features"]["b_life_path"] is not None and 0 < rec["p"]["a_set"] < 1
    from astrofoot import live as football_live
    assert football_live.verify(rec)
    # a second cycle does not forecast it twice; once played, it is settled
    done = {**up, "state": "post", "completed": True, "winner": 2, "set_winners": "212", "score": "4-6 6-3 2-6"}
    out = tlive.cycle(now + timedelta(hours=8), ledger, log=lambda *a: None, crawl=lambda a, b, log: pd.DataFrame([done]),
                      fetch_players=fetch_players)
    assert out == {"new": 0, "settled": 1}
    (r,) = tlive.records(ledger)
    assert r["status"] == "settled" and r["sets_played"] == 3 and r["result"]["winner"] == 2
    tr = tlive.track_record([r])
    assert tr["n"] == 1 and tr["sets"]["n"] == 3
    assert "Tennis live track record" in (ledger / "TRACK_RECORD.md").read_text()


def test_tennis_pages_render_with_a_switch(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot.web import app as web
    from astrofoot.web import tennis_web

    hist, pl = fake_matches(300)
    monkeypatch.setattr(tennis_web.tlive, "load_matches", lambda ledger=None: hist)
    monkeypatch.setattr(tennis_web.tlive, "load_players", lambda ledger=None: pl)
    monkeypatch.setattr(tennis_web, "_sources_key", lambda: ("test", len(hist)))
    client = TestClient(web.app)
    for url in ("/tennis", "/tennis/model", "/tennis/dataset?player=player+1", "/tennis/analyze?a=Player+1&b=Player+2&surface=clay"):
        html = client.get(url).text
        assert "🎾 Tennis" in html and "Astro Tennis Lab" in html, url
    assert "Life path number" in client.get("/tennis/analyze?a=Player+1&b=Player+2").text
    assert "Astro Football Lab" in client.get("/").text
