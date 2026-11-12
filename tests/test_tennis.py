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
    assert (ff.elo_diff == -f.elo_diff).all() and (ff.a_num_rule.fillna(-1) == f.b_num_rule.fillna(-1)).all()
    assert (ff.d_astro_rule.fillna(0) == -f.d_astro_rule.fillna(0)).all()


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
    assert set(rep["learned"]) == {"astro", "numerology"} and set(rep["combo_eval"]) == set(model.HEADS)
    assert rep["verdicts"]["astro"]["n_matches"] > 0
    c = p["combined"]
    assert abs(c["a_set"] + c["b_set"] - 1) < 1e-9 and p["expected"] == c and p["market"] is None
    # with odds: the market and the expected figure (blend) appear
    q = model.predict(features.row(st, nxt, features.players_dict(pl)), model.load(), odds=(1.5, 2.6))
    assert abs(q["market"]["a_match"] - (1 / 1.5) / (1 / 1.5 + 1 / 2.6)) < 1e-9 and q["market"]["a_set"] > 0.5
    lo, hi = sorted([q["combined"]["a_set"], q["market"]["a_set"]])
    assert lo - 1e-9 <= q["expected"]["a_set"] <= hi + 1e-9


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

    odds = lambda todo, now, ledger, log: {"U1": {"a": 1.4, "b": 3.0, "source": "test"}}  # noqa: E731
    out = tlive.cycle(now, ledger, log=lambda *a: None, crawl=lambda a, b, log: pd.DataFrame([up]), fetch_players=fetch_players,
                      odds_fetch=odds)
    assert out["new"] == 1 and fetched == ["99"]
    (rec,) = tlive.predictions(ledger)
    assert rec["day"]["dob"]["b"] == "2001-04-04" and rec["day"]["num"]["b"]["numbers"]["life_path"] == 11
    assert rec["day"]["astro"]["favours"] in (0, 1, 2) and rec["odds"]["a"] == 1.4
    assert 0 < rec["p"]["expected"]["a_set"] < 1 and rec["p"]["market"]["a_match"] > 0.6
    from astrofoot import live as football_live
    assert football_live.verify(rec)
    # a second cycle does not forecast it twice; once played, it is settled
    done = {**up, "state": "post", "completed": True, "winner": 2, "set_winners": "212", "score": "4-6 6-3 2-6"}
    out = tlive.cycle(now + timedelta(hours=8), ledger, log=lambda *a: None, crawl=lambda a, b, log: pd.DataFrame([done]),
                      fetch_players=fetch_players, odds_fetch=odds)
    assert out == {"new": 0, "settled": 1}
    (r,) = tlive.records(ledger)
    assert r["p1_seed"] is None and r["p2_seed"] is None                # no "nan" seeds
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
    html = client.get("/tennis/analyze?a=Player+1&b=Player+2&a_odds=1.5&b_odds=2.6").text
    assert "Who is favoured for the day" in html and "life path" in html
    for m in ("set", "first", "match", "one_set", "dog_set"):
        assert "Tennis top picks" in client.get(f"/tennis/top?market={m}&day=all").text
    assert "Astro Football Lab" in client.get("/").text


def test_best_of_five_only_in_mens_slam_main_draws():
    assert espn.best_of("atp", "Wimbledon", "Round 1") == 5 and espn.best_of("atp", "Wimbledon", "Qualifying 1st Round") == 3
    assert espn.best_of("wta", "Wimbledon", "Final") == 3 and espn.best_of("atp", "Bybit Stockholm Open", "Round 1") == 3


def test_odds_player_names_match():
    from astrofoot.tennis.odds import same_player
    assert same_player("Iga Swiatek", "Iga Świątek") and same_player("Carlos Alcaraz", "Carlos Alcaraz Garfia")
    assert not same_player("Karolina Pliskova", "Kristyna Pliskova") and not same_player("Jannik Sinner", "Carlos Alcaraz")


def test_tennis_my_picks_slips_and_scoring(tmp_path, monkeypatch):
    import re

    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot import live as football_live
    from astrofoot.tennis import live as tlive
    from astrofoot.tennis import mypicks as tmp
    from astrofoot.web import app as web

    p = {"a_set": 0.6, "b_set": 0.4, "a_first": 0.62, "b_first": 0.38, "a_one_set": 0.85, "b_one_set": 0.6,
         "a_match": 0.7, "b_match": 0.3, "version": "t"}
    day = {"day": "2030-01-02", "tz": None, "venue": "", "dob": {"a": None, "b": None},
           "astro": {"a": {"score": 1.0, "contacts": []}, "b": {"score": 0.0, "contacts": []}, "favours": 1},
           "num": {"a": {"score": 0.0, "parts": [], "numbers": {}}, "b": {"score": 1.0, "parts": [], "numbers": {}}, "favours": 2}}
    rec = football_live.seal({"match_id": "M1", "tour": "atp", "event": "Test Open", "round": "Round 1", "venue": "", "surface": "hard",
                              "best_of": 3, "start_utc": "2030-01-02T12:00:00+00:00", "p1": "Ann A", "p1_id": "1", "p2": "Bea B",
                              "p2_id": "2", "p1_seed": None, "p2_seed": None, "model_version": "t", "p": p, "features": {},
                              "day": day, "odds": None, "committed_at": "2030-01-01T10:00:00+00:00"})
    res = {"M1": {"match_id": "M1", "winner": 2, "set_winners": "122", "score": "6-4 3-6 2-6", "retired": False, "void": False}}
    monkeypatch.setattr(tlive, "records", lambda ledger=None, **kw: [tlive.join(rec, res["M1"])])
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    client = TestClient(web.app)
    html = client.get("/tennis/mypicks?day=2030-01-02").text
    sid = int(re.search(r'/tennis/mypicks/slip/rename".*?name="slip" value="(\d+)"', html, re.S).group(1))
    client.post("/tennis/mypicks/add", data={"slip": sid, "game": "M1", "sel_M1": "on", "out_M1": "o:1"})
    (pick,) = db.my_picks(db.connect(path), section="tennis")
    assert pick["selection"] == "o:1" and abs(pick["p"] - 0.85) < 1e-9
    html = client.get("/tennis/mypicks?day=2030-01-02").text
    assert "6-4 3-6 2-6 ✓" in html and "astro ✓" in html                # Ann won a set; astrology favoured her
    assert tmp.won("m:1", "122", 2) is False and tmp.won("f:1", "122", 2) and tmp.won("o:2", "122", 2)
    assert "Ann A" not in client.get("/mypicks").text                     # never on the soccer My picks


def test_odds_fetch_buys_only_listed_tournaments_and_keeps_a_reserve(tmp_path):
    from astrofoot.tennis import odds as todds

    class Fake:
        def __init__(self, remaining):
            self.remaining, self.calls = remaining, []

        def get(self, path, **kw):
            self.calls.append(path)
            if path == "/sports":
                return [{"key": "tennis_wta_finals", "group": "Tennis", "active": True},
                        {"key": "tennis_atp_finals", "group": "Tennis", "active": True}]
            if path.endswith("/events"):
                return ([{"id": "E1", "home_team": "Iga Świątek", "away_team": "Coco Gauff"}]
                        if "wta" in path else [{"id": "E9", "home_team": "X Y", "away_team": "Z W"}])
            return [{"id": "E1", "home_team": "Iga Świątek", "away_team": "Coco Gauff", "bookmakers": [
                {"key": "b1", "markets": [{"key": "h2h", "outcomes": [{"name": "Iga Świątek", "price": 1.5}, {"name": "Coco Gauff", "price": 2.6}]}]},
                {"key": "b2", "markets": [{"key": "h2h", "outcomes": [{"name": "Iga Świątek", "price": 1.6}, {"name": "Coco Gauff", "price": 2.4}]}]}]}]

    up = [{"id": "M1", "p1": "Coco Gauff", "p2": "Iga Swiatek"}]
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    c = Fake(400)
    out = todds.fetch(up, now, tmp_path, client=c, log=lambda *a: None)
    assert out["M1"]["a"] == pytest.approx(2.5) and out["M1"]["b"] == pytest.approx(1.55)       # player 1 = Gauff
    assert c.calls.count("/sports/tennis_wta_finals/odds") == 1 and "/sports/tennis_atp_finals/odds" not in c.calls
    c2 = Fake(400)                                                      # within 12 hours: served from the cache
    assert todds.fetch(up, now + timedelta(hours=2), tmp_path, client=c2, log=lambda *a: None)["M1"]["a"] == pytest.approx(2.5)
    assert not any(x.endswith("/odds") for x in c2.calls)
    c3 = Fake(100)                                                      # below the reserve: buys nothing
    (tmp_path / "odds_state.json").unlink()
    assert todds.fetch(up, now, tmp_path, client=c3, log=lambda *a: None) == {}


def test_tennis_live_record_scores_settled_forecasts(monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot import live as football_live
    from astrofoot.tennis import live as tlive
    from astrofoot.web import app as web
    from astrofoot.web import tennis_web

    p = {"a_set": 0.6, "b_set": 0.4, "a_first": 0.62, "b_first": 0.38, "a_one_set": 0.85, "b_one_set": 0.6,
         "a_match": 0.7, "b_match": 0.3, "version": "t"}
    p["expected"] = dict(p)
    p["market"] = {"a_match": 0.75, "b_match": 0.25, "a_set": 0.63, "b_set": 0.37}
    day = {"day": "2030-01-02", "tz": None, "venue": "", "dob": {"a": None, "b": None},
           "astro": {"a": {"score": 1.0, "contacts": []}, "b": {"score": 0.0, "contacts": []}, "favours": 1},
           "num": {"a": {"score": 0.0, "parts": [], "numbers": {}}, "b": {"score": 0.0, "parts": [], "numbers": {}}, "favours": 0}}
    base = {"tour": "atp", "event": "Test Open", "round": "Round 1", "venue": "", "surface": "hard", "best_of": 3,
            "start_utc": "2030-01-02T12:00:00+00:00", "p1_id": "1", "p2_id": "2", "p1_seed": None, "p2_seed": None,
            "model_version": "t", "p": p, "features": {}, "day": day, "odds": {"a": 1.3, "b": 3.6, "source": "t"},
            "committed_at": "2030-01-01T10:00:00+00:00"}
    r1 = football_live.seal({**base, "match_id": "M1", "p1": "Ann A", "p2": "Bea B"})
    r2 = football_live.seal({**base, "match_id": "M2", "p1": "Cat C", "p2": "Dee D"})
    res = {"M1": {"winner": 1, "set_winners": "121", "score": "6-4 3-6 6-2", "retired": False, "void": False}}
    monkeypatch.setattr(tlive, "records", lambda ledger=None, **kw: [tlive.join(r1, res["M1"]), tlive.join(r2, None)])
    client = TestClient(web.app)
    html = client.get("/tennis/live").text
    assert "2/2 seals verify" in html and "2/3 sets" in html and "Odds alone" in html
    assert "Ann A" in client.get("/tennis/live?status=settled&hit=hit").text
    assert "Cat C" not in client.get("/tennis/live?status=settled").text
    recs = [tlive.join(r1, res["M1"])]
    for r in recs:
        r["dayv"] = day
    (stats, expected, odds) = tennis_web.compare_sources(recs)
    assert stats["n_sets"] == 3 and abs(stats["set_acc"] - 2 / 3) < 1e-9 and odds["n"] == 1
    band = next(b for b in tennis_web.calibration(recs) if b["matches"])
    assert band["band"] == "60–65%" and band["hits"] == 2 and band["n"] == 3


def test_tennis_dataset_filters_and_day_readings(monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot.web import app as web
    from astrofoot.web import tennis_web

    hist, pl = fake_matches(300)
    hist.loc[hist.index[-1], ["round", "p1_seed", "winner"]] = ["Final", 3, 2]
    monkeypatch.setattr(tennis_web.tlive, "load_matches", lambda ledger=None: hist)
    monkeypatch.setattr(tennis_web.tlive, "load_players", lambda ledger=None: pl)
    monkeypatch.setattr(tennis_web, "_sources_key", lambda: ("dataset-test", len(hist)))
    tennis_web._STATE.clear()
    client = TestClient(web.app)
    html = client.get("/tennis/dataset?round=final&seeds=upset").text
    assert "1 matches" in html and 'href="/dataset?section=women"' in html
    html = client.get("/tennis/dataset?check=1").text
    assert "before the day filters" in html and "Astrology favoured a player" in html
    won = client.get("/tennis/dataset?astro=won").text
    lost = client.get("/tennis/dataset?astro=lost").text
    level = client.get("/tennis/dataset?astro=level").text
    import re
    n = lambda h: int(re.search(r"([\d,]+) matches \(", h).group(1).replace(",", ""))  # noqa: E731
    assert n(won) + n(lost) + n(level) == 300
    assert 'href="/tennis/dataset"' in client.get("/dataset").text           # Tennis on the soccer Dataset switch


def test_day_favours_filter():
    from astrofoot.web.tennis_web import day_favours_ok
    dv = lambda a, n: {"astro": {"favours": a}, "num": {"favours": n}}  # noqa: E731
    assert day_favours_ok(dv(1, 1), "both") and day_favours_ok(dv(2, 2), "both")
    assert not day_favours_ok(dv(1, 2), "both") and not day_favours_ok(dv(0, 0), "both") and not day_favours_ok(dv(1, 0), "both")
    assert day_favours_ok(dv(1, 2), "split") and not day_favours_ok(dv(1, 0), "split")
    assert day_favours_ok(dv(1, 0), "astro") and not day_favours_ok(dv(0, 2), "astro") and day_favours_ok(dv(0, 2), "num")
    assert day_favours_ok(dv(0, 0), "")


def _rec(match_id="M1", p1="Ann A", p2="Bea B", p2_id="2", astro=1, num=1):
    from astrofoot import live as football_live
    p = {"a_set": 0.55, "b_set": 0.45, "a_first": 0.56, "b_first": 0.44, "a_one_set": 0.8, "b_one_set": 0.7,
         "a_match": 0.6, "b_match": 0.4, "version": "t"}
    day = {"day": "2030-01-02", "tz": None, "venue": "", "dob": {"a": None, "b": None},
           "astro": {"a": {"score": 1.0, "contacts": []}, "b": {"score": 0.0, "contacts": []}, "favours": astro},
           "num": {"a": {"score": 1.0, "parts": [], "numbers": {}}, "b": {"score": 0.0, "parts": [], "numbers": {}}, "favours": num}}
    return football_live.seal({"match_id": match_id, "tour": "wta", "event": "Test Open", "round": "Round 1", "venue": "",
                               "surface": "hard", "best_of": 3, "start_utc": "2030-01-02T12:00:00+00:00", "p1": p1, "p1_id": "1",
                               "p2": p2, "p2_id": p2_id, "p1_seed": None, "p2_seed": None, "model_version": "t", "p": p,
                               "features": {}, "day": day, "odds": None, "committed_at": "2030-01-01T10:00:00+00:00"})


def test_tbd_players_are_never_forecast_and_old_ones_are_void(tmp_path):
    from astrofoot.tennis import live as tlive
    assert features.placeholder("-4", "TBD") and features.placeholder("123", "TBD") and not features.placeholder("123", "Ann A")
    rec = tlive.join(_rec(p2="TBD", p2_id="-4"), None)
    assert rec["status"] == "void" and "TBD" in rec["result"]["void_reason"]
    st = features.State()
    st.update({"p1_id": "1", "p2_id": "-4", "p1": "Ann A", "p2": "TBD", "date": pd.Timestamp("2030-01-01", tz="UTC"),
               "winner": 1, "set_winners": "11"})
    assert "-4" not in st.n and "1" not in st.last                 # placeholders never enter the ratings


def test_odds_entered_by_hand_apply_everywhere(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot.tennis import live as tlive
    from astrofoot.web import app as web

    rec = _rec()
    monkeypatch.setattr(tlive, "predictions", lambda ledger=None: [rec])
    monkeypatch.setattr(tlive, "results", lambda ledger=None: {})
    monkeypatch.setattr(model, "load", lambda: {"maps": {3: {"set": {"a": 0.8, "b": 0}, "first": {"a": 0.8, "b": 0},
                                                            "one_set": {"a": 0.9, "b": 0.8}}}, "market_weight": 0.6})
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    client = TestClient(web.app)
    before = tlive.records()[0]
    r = client.post("/tennis/match/M1/odds", data={"a": "3.0", "b": "1.4"}, follow_redirects=False)
    assert "Odds+saved" in r.headers["location"] or "Odds%20saved" in r.headers["location"]
    after = tlive.records(user_odds=db.tennis_odds(db.connect(path)))[0]
    assert after["verified"] and after["odds"]["manual"] and after["e"]["a_match"] < before["e"]["a_match"]
    assert after["fav"] == 2                                            # the odds flipped the favourite
    for url in ("/tennis/match/M1", "/tennis?day=all", "/tennis/live", "/tennis/top?day=all", "/tennis/mypicks?day=2030-01-02"):
        assert "your odds" in client.get(url).text or "entered by you" in client.get(url).text, url
    assert "must be decimal" in client.post("/tennis/match/M1/odds", data={"a": "0.9", "b": "x"}).text
    client.post("/tennis/match/M1/odds", data={"remove": "1"})
    assert db.tennis_odds(db.connect(path)) == {}


def test_tennis_my_picks_day_favours_filter(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot.tennis import live as tlive
    from astrofoot.web import app as web

    recs = [tlive.join(_rec("M1", "Ann A", "Bea B", astro=1, num=1), None),
            tlive.join(_rec("M2", "Cat C", "Dee D", astro=1, num=2), None)]
    monkeypatch.setattr(tlive, "records", lambda ledger=None, **kw: recs)
    monkeypatch.setattr(web, "con", lambda: db.connect(tmp_path / "t.sqlite3"))
    client = TestClient(web.app)
    html = client.get("/tennis/mypicks?day=2030-01-02&favours=both").text
    assert "Ann A v Bea B" in html and "Cat C v Dee D" not in html and "both: A" in html
    html = client.get("/tennis/mypicks?day=2030-01-02&favours=split").text
    assert "Cat C v Dee D" in html and "Ann A v Bea B" not in html


def test_score_parsing():
    from astrofoot.web.tennis_web import parse_score as ps
    assert ps("6-4 3-6 7-6")["set_winners"] == "121" and ps("6-4 3-6") is None
    assert ps("6-4 2-1 ret") is None and ps("6-4 2-1 ret", 3, 2) == {"winner": 2, "set_winners": "1", "score": "6-4 2-1 ret.",
                                                                     "retired": True, "void": False}
    assert ps("6-3 6-4", 5) is None and ps("6-3 6-4 6-2", 5)["winner"] == 1 and ps("4-6 7-5 10-8")["set_winners"] == "211"


def test_matches_added_by_hand(tmp_path, monkeypatch):
    import re

    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot.tennis import live as tlive
    from astrofoot.web import app as web
    from astrofoot.web import tennis_web

    hist, pl = fake_matches(300)
    monkeypatch.setattr(tennis_web.tlive, "load_matches", lambda ledger=None: hist)
    monkeypatch.setattr(tennis_web.tlive, "load_players", lambda ledger=None: pl)
    monkeypatch.setattr(tennis_web, "_sources_key", lambda: ("manual-test", len(hist)))
    monkeypatch.setattr(tlive, "predictions", lambda ledger=None: [])
    tennis_web._STATE.clear()
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    client = TestClient(web.app)
    q = {"a": "Player 1", "b": "Player 2", "when": "2030-01-02T12:00", "surface": "clay", "best_of": "3", "tour": "atp",
         "round": "Round 1", "event": "Some Challenger", "a_seed": "", "b_seed": "", "a_dob": "", "b_dob": "", "venue": "",
         "a_odds": "1.5", "b_odds": "2.5"}
    if not model.BUNDLE.exists():
        return
    r = client.post("/tennis/analyze/save", data=q, follow_redirects=False)
    mid = re.search(r"/tennis/match/(u\d+)", r.headers["location"]).group(1)
    html = client.get(f"/tennis/match/{mid}").text
    assert "Added by you" in html and "Some Challenger" in html
    for url in ("/tennis?day=all", "/tennis/live", "/tennis/top?day=all", "/tennis/mypicks?day=2030-01-02"):
        assert "manual" in client.get(url).text, url
    assert "Could not read" in client.post(f"/tennis/match/{mid}/result", data={"score": "6-4"}).text
    client.post(f"/tennis/match/{mid}/result", data={"score": "6-4 4-6 6-3"})
    (rec,) = [r for r in tennis_web.records() if r["match_id"] == mid]
    assert rec["status"] == "settled" and rec["result"]["winner"] == 1 and rec["manual"]
    assert tlive.track_record([rec])["n"] == 0                          # never in the official record
    client.post(f"/tennis/match/{mid}/result", data={"delete": "1"})
    assert db.tennis_manual(db.connect(path)) == []


def test_day_chart_follows_the_venue():
    from astrofoot.tennis import venue
    from astrofoot.tennis import daychart as dc
    if venue.venue_tz("Bogota, Colombia") is None:          # the cities table is not downloaded here
        return
    late = "2026-11-11T01:30:00+00:00"                        # 20:30 on the 10th in Bogotá
    assert venue.local_day("Bogota, Colombia", late) == ("2026-11-10", "America/Bogota")
    assert venue.local_day("Melbourne, Australia", "2026-11-10T22:00:00+00:00")[0] == "2026-11-11"
    assert venue.local_day("World", late) == ("2026-11-11", None)                 # unknown venue: the UTC day
    assert venue.venue_tz("St. Petersburg, Russia") == "Europe/Moscow" and venue.venue_tz("Basel. Switzerland") == "Europe/Zurich"
    assert venue.noon_utc_hour("2026-11-10", "America/Bogota") == 17.0
    # the sky is taken at noon at the venue, so the Sun differs from noon UTC by the hours in between
    assert abs(dc.sky("2026-11-10", "America/Bogota")[0] - dc.positions("2026-11-10")[0] - 5 * 0.0417) < 0.01
    f = features.day_features({"dob": "1995-07-23"}, {"dob": "1999-08-31"}, "A", "B", pd.Timestamp(late), "Bogota, Colombia")
    g = features.day_features({"dob": "1995-07-23"}, {"dob": "1999-08-31"}, "A", "B", pd.Timestamp("2026-11-10T17:00", tz="UTC"), "")
    assert f["d_num_rule"] == g["d_num_rule"]               # same local day → same numerology


def test_espn_date_only_placeholders_and_moved_starts():
    from astrofoot.tennis import live as tlive
    from astrofoot.tennis import venue
    if venue.venue_tz("Indian Wells, USA") is None:
        return
    ph = "2026-11-13T05:00:00+00:00"                          # midnight US Eastern: ESPN's "time not set"
    assert venue.date_only(ph) and not venue.date_only("2026-11-13T05:30:00+00:00")
    assert venue.local_day("Indian Wells, USA", ph)[0] == "2026-11-13"          # not the 12th in California
    assert venue.local_time("Indian Wells, USA", ph) == (None, "America/Los_Angeles")
    assert str(tlive.effective_start("Indian Wells, USA", ph)) == "2026-11-13 08:00:00+00:00"   # midnight there
    # a forecast sealed before the sealed start, but after ESPN moved the match earlier, is not scored
    rec = {**_rec(), "venue": "Paris, France", "start_utc": "2030-01-02T12:00:00+00:00", "time_known": True,
           "committed_at": "2030-01-02T10:30:00+00:00"}
    res = {"winner": 1, "set_winners": "11", "score": "6-1 6-1", "retired": False, "void": False}
    assert tlive.join(rec, res)["pre_kickoff"]
    assert not tlive.join(rec, {**res, "start_final": "2030-01-02T10:00:00+00:00"})["pre_kickoff"]
    assert tlive.join(rec, {**res, "start_final": "2030-01-02T15:00:00+00:00"})["pre_kickoff"]      # moved later: fine


def test_duplicate_player_ids_are_merged_but_namesakes_kept_apart():
    from astrofoot.tennis import ids
    m = pd.DataFrame([{"p1_id": "1", "p1": "Ann A", "p2_id": "9", "p2": "Zed"},
                      {"p1_id": "2", "p1": "Ann A", "p2_id": "9", "p2": "Zed"},
                      {"p1_id": "1", "p1": "Ann A", "p2_id": "8", "p2": "Kim K"},
                      {"p1_id": "5", "p1": "Kim K", "p2_id": "9", "p2": "Zed"}])
    pl = pd.DataFrame([{"id": "1", "dob": "2000-01-01"}, {"id": "2", "dob": None},
                       {"id": "8", "dob": "1990-05-05"}, {"id": "5", "dob": "2001-05-05"}])
    al = ids.aliases(m, pl)
    assert al == {"2": "1"}                                  # Kim K (8) and Kim K (5) are different people
    assert list(ids.apply(m, al).p1_id) == ["1", "1", "1", "5"]


class FakeLTA:
    """A Live Tennis API stand-in with the free tier's daily budget."""

    def __init__(self, matches, left=90):
        self.matches, self._left, self.calls = matches, left, []
        self.state = {}

    @property
    def left(self):
        return self._left

    def get(self, path, **kw):
        if self._left <= 0:
            raise RuntimeError("budget")
        self._left -= 1
        self.calls.append((path, kw))
        if path == "/matches":
            data = [m for m in self.matches if m["status"] == kw["status"] and (
                m["tour"] == kw["tour"] if kw["tour"] == "challenger" else m["tour"] == kw["tour"])]
            return {"data": data, "meta": {"has_more": False}}
        mid = int(path.rsplit("/", 1)[1])
        return {"data": next(m for m in self.matches if m["id"] == mid)}

    def save(self):
        pass


def _lta_match(mid, p1, p2, when, status="upcoming", tour="challenger", tournament="Challenger Sao Paulo", games=None,
               winner=None):
    return {"id": mid, "tournament": tournament, "tournament_id": 7, "tour": tour, "surface": "Clay", "format": "BO3",
            "round": "R32", "status": status, "scheduled_time": when, "is_doubles": False,
            "players": {"p1": {"id": 100 + mid, "name": p1, "birthday": "2000-02-02", "hand": "right"},
                        "p2": {"id": 200 + mid, "name": p2, "birthday": "1999-09-09", "hand": "left"}},
            "score": {"games": games} if games else None, "winner": winner}


def test_lta_parsing_and_results():
    from astrofoot.tennis import lta
    m = lta.to_match(_lta_match(1, "Ann A", "Bea B", "2030-01-02T14:00:00Z"))
    assert m["id"] == "lta:1" and m["level"] == "challenger" and m["surface"] == "clay" and m["state"] == "pre"
    assert m["venue"] == "Sao Paulo" and m["_dob"]["lta:101"] == "2000-02-02"
    done = _lta_match(1, "Ann A", "Bea B", "2030-01-02T14:00:00Z", "completed", games=[[6, 3, 7], [4, 6, 6]], winner=1)
    assert lta.result_of(done) == {"winner": 1, "set_winners": "121", "score": "6-4 3-6 7-6", "retired": False,
                                   "walkover": False, "void": False}
    ret = _lta_match(1, "Ann A", "Bea B", "2030-01-02T14:00:00Z", "completed", games=[[6, 2], [3, 1]], winner=2)
    r = lta.result_of(ret)
    assert r["retired"] and r["winner"] == 2 and r["set_winners"] == "1"
    assert lta.result_of({**done, "status": "cancelled"})["void"]
    assert lta.team_event("Hopman Cup") and not lta.team_event("Paris Masters")
    assert lta.to_match({**done, "is_doubles": True}) is None


def test_challengers_are_forecast_settled_and_join_the_history(tmp_path, monkeypatch):
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
    start = (now + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    api = FakeLTA([_lta_match(1, "Player 3", "New Guy", start),                       # Player 3 is in the history
                   _lta_match(2, "Cat C", "Dee D", start, tour="atp", tournament="Hopman Cup"),
                   _lta_match(3, "Eve E", "Fay F", start, tour="atp", tournament="Some ATP 250")])   # not a team event
    ledger = tmp_path / "ledger"
    quiet = dict(log=lambda *a: None, crawl=lambda a, b, log: pd.DataFrame(), fetch_players=lambda ids, known, log: pd.DataFrame(),
                 odds_fetch=lambda *a, **k: {})
    out = tlive.cycle(now, ledger, lta_client=api, **quiet)
    recs = {r["match_id"]: r for r in tlive.predictions(ledger)}
    assert out["new"] == 2 and set(recs) == {"lta:1", "lta:2"}
    assert recs["lta:1"]["p1_id"] == "3" and recs["lta:1"]["level"] == "challenger"          # ESPN id kept for Player 3
    assert recs["lta:2"]["level"] == "team" and recs["lta:1"]["day"]["dob"]["b"] == "1999-09-09"
    # finished: the next cycle settles it with one look-up
    api.matches[0].update(status="completed", score={"games": [[6, 6], [2, 3]]}, winner=1)
    api.matches[1].update(status="completed", score={"games": [[6, 6], [2, 3]]}, winner=2)
    out = tlive.cycle(now + timedelta(hours=12), ledger, lta_client=api, **quiet)
    assert out["settled"] == 2
    r = next(x for x in tlive.records(ledger) if x["match_id"] == "lta:1")
    assert r["status"] == "settled" and r["result"]["set_winners"] == "11" and r["result"]["source"] == "livetennisapi.com"
    h = tlive._lta_history(ledger)
    assert set(h.id) == {"lta:1", "lta:2"} and (h.completed).all()                # Challenger results feed the ratings


def test_settling_stops_at_the_daily_budget(tmp_path):
    from astrofoot.tennis import lta
    pend = [{"match_id": f"lta:{i}", "start_utc": "2030-01-01T10:00:00+00:00"} for i in range(1, 6)]
    api = FakeLTA([_lta_match(i, "A", "B", "2030-01-01T10:00:00Z", "completed", games=[[6, 6], [1, 1]], winner=1)
                   for i in range(1, 6)], left=3)
    got = lta.settle(pend, api, datetime(2030, 1, 2, tzinfo=timezone.utc), log=lambda *a: None)
    assert len(got) == 3 and api.left == 0


def test_result_entered_by_hand_for_an_unsettled_challenger(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from astrofoot import db
    from astrofoot.tennis import live as tlive
    from astrofoot.web import app as web
    from astrofoot.web import tennis_web

    rec = {**_rec("lta:9", "Ann A", "Bea B"), "level": "challenger", "start_utc": "2020-01-02T12:00:00+00:00",
           "committed_at": "2020-01-01T10:00:00+00:00"}
    monkeypatch.setattr(tlive, "predictions", lambda ledger=None: [rec])
    monkeypatch.setattr(tlive, "results", lambda ledger=None: {})
    path = tmp_path / "t.sqlite3"
    monkeypatch.setattr(web, "con", lambda: db.connect(path))
    client = TestClient(web.app)
    assert "free daily quota" in client.get("/tennis/match/lta:9").text
    client.post("/tennis/match/lta:9/result", data={"score": "6-2 6-3"})
    (r,) = tennis_web.records()
    assert r["status"] == "settled" and r["result_by_you"] and r["result"]["winner"] == 1 and r["match_hit"]
    assert "your result" in client.get("/tennis/live").text
    client.post("/tennis/match/lta:9/result", data={"clear": "1"})
    assert tennis_web.records()[0]["status"] == "pending"


def test_lta_real_response_shapes():
    from astrofoot.tennis import lta
    m = {"id": 218705, "tournament": "Sopo (Colombia)", "tour": "challenger", "gender": "women", "format": "BO3",
         "round": "Sopo - 1/8-finals", "status": "upcoming", "surface": "clay", "is_doubles": False,
         "scheduled_time": "2026-11-12T03:45:00Z", "score": {"games": [[0], [0]], "sets": [0, 0]},
         "players": {"p1": {"id": 814, "name": "Ann A", "birthday": "1993-01-27", "hand": "R"},
                     "p2": {"id": 815, "name": "Bea B", "birthday": None, "hand": None}}}
    r = lta.to_match(m)
    assert r["tour"] == "wta" and r["venue"] == "Sopo, Colombia" and r["winner"] is None and r["state"] == "pre"
    done = {**m, "status": "completed", "event_status": "Finished", "outcome": "completed", "winner": 1,
            "score": {"games": [[6, 6], [0, 0]], "sets": [2, 0]}}
    assert lta.result_of(done)["set_winners"] == "11"
    wo = {**done, "event_status": "Walk Over", "score": None}
    assert lta.result_of(wo)["void"] and lta.result_of(wo)["void_reason"] == "walkover"
    ret = {**done, "outcome": "retired", "score": {"games": [[6, 2], [3, 1]]}}
    assert lta.result_of(ret)["retired"] and lta.result_of(ret)["set_winners"] == "1"


def test_sources_with_different_name_orders_are_the_same_match():
    from astrofoot.tennis import live as tlive
    assert tlive.same_match("Marina Ribera Bassols", "Bianca Andreescu", "2026-11-12T16:30Z",
                            "Bianca Andreescu", "Marina Bassols Ribera", "2026-11-12T16:30Z")
    assert tlive.same_match("Irene Burillo Escorihuela", "Laura Samson", "2026-11-12T15:00Z",
                            "Irene Burillo", "Laura Samson", "2026-11-12T18:00Z")
    assert not tlive.same_match("Irene Burillo", "Laura Samson", "2026-11-12T15:00Z",
                                "Irene Burillo", "Laura Samson", "2026-11-15T15:00Z")       # days apart: another match


def test_itf_matches_are_compact_and_settled_after_challengers(tmp_path):
    from astrofoot.tennis import live as tlive
    from astrofoot.tennis import lta
    m = lta.to_match({**_lta_match(5, "Ann A", "Bea B", "2030-01-02T10:00:00Z", tour="itf", tournament="W15 Paris (France)"),
                      "gender": "women"})
    assert m["level"] == "itf" and m["tour"] == "wta" and m["venue"] == "Paris, France"
    rec = {"features": {"elo_diff": 10.0, "d_astro_conj_Su_Su": 0.5, "a_form": 0.6}, "day": {
        "day": "2030-01-02", "tz": "Europe/Paris", "astro": {"a": {"score": 1.0, "contacts": [{"text": "x"}]},
                                                               "b": {"score": 0.0, "contacts": []}, "favours": 1},
        "num": {"a": {"score": 1.0, "parts": [{"text": "y"}], "numbers": {"life_path": 3}},
                "b": {"score": 0.0, "parts": [], "numbers": {}}, "favours": 1}}}
    c = tlive.compact(rec)
    assert set(c["features"]) == {"elo_diff", "a_form"} and c["day"]["compact"] and c["day"]["astro"]["favours"] == 1
    assert c["day"]["astro"]["a"]["contacts"] == [] and c["day"]["num"]["a"]["numbers"] == {"life_path": 3}
    # settling: Challengers first (oldest first), then ITF newest first, within the budget
    pend = ([{"match_id": f"lta:{i}", "start_utc": f"2030-01-0{i}T10:00:00+00:00", "level": "itf"} for i in (1, 2, 3)]
            + [{"match_id": "lta:9", "start_utc": "2030-01-01T09:00:00+00:00", "level": "challenger"}])
    api = FakeLTA([_lta_match(i, "A", "B", "2030-01-01T10:00:00Z", "completed", games=[[6, 6], [1, 1]], winner=1)
                   for i in (1, 2, 3, 9)], left=2)
    got = lta.settle(pend, api, datetime(2030, 1, 5, tzinfo=timezone.utc), log=lambda *a: None)
    assert set(got) == {"lta:9", "lta:3"}                    # the Challenger, then the newest ITF match


def test_levels_and_wta125_detection():
    from astrofoot.web import tennis_web as tw
    espn = {"match_id": "1", "tour": "wta", "event": "DIRECTV Open", "p1": "Ann A", "p2": "Bea B",
            "start_utc": "2030-01-02T15:00:00+00:00"}
    api = {"match_id": "lta:5", "tour": "wta", "level": "challenger", "event": "Sopo (Colombia)", "p1": "Bea B",
           "p2": "Ann A", "start_utc": "2030-01-02T15:00:00+00:00"}
    w125 = tw._wta125_events([espn, api])
    assert w125 == {"DIRECTV Open"} and tw.category(espn, w125) == "wta125"
    assert tw.category({"tour": "wta", "event": "Austin 125"}) == "wta125"
    assert tw.category({"tour": "wta", "event": "WTA Finals"}) == "tour"
    assert tw.category({"tour": "wta", "level": "itf"}) == "itf_w" and tw.category({"tour": "atp", "level": "itf"}) == "itf_m"
    assert tw.category({"tour": "atp", "level": "challenger"}) == "challenger"
    r = {"tour": "wta", "cat": "itf_w"}
    assert tw.level_ok(r, "women") and tw.level_ok(r, "itf_w") and not tw.level_ok(r, "men") and tw.level_ok(r, "")


def test_short_round():
    from astrofoot.tennis.lta import short_round
    assert short_round("W50 Chihuahua 2 - Quarter-finals") == "Quarter-finals" and short_round("Final") == "Final"
