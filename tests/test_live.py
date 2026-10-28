import json
from datetime import datetime, timezone

import pandas as pd

from astrofoot import live

CSV = (b"\xef\xbb\xbfDiv,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A,B365>2.5,B365<2.5\n"
       b"E0,08/11/2026,15:00,Arsenal,Chelsea,1.80,3.80,4.40,1.70,2.20\n"
       b"E0,08/11/2026,,Fulham,Brentford,2.10,3.40,3.50,1.90,1.95\n"        # no kickoff time -> skipped
       b"E0,09/11/2026,16:30,Everton,Wolves,,,,1.90,1.95\n"                  # no odds -> skipped
       b"XX,09/11/2026,16:30,Foo,Bar,2.0,3.0,4.0,1.9,1.9\n")                  # unknown league -> skipped


def test_parse_fixtures_converts_uk_time_and_filters():
    fx = live.parse_fixtures(live.read_csv_bytes(CSV))
    assert len(fx) == 1
    f = fx[0]
    assert f["kickoff_utc"] == "2026-11-08T15:00:00+00:00"        # GMT in November
    assert f["odds_source"].endswith("B365") and 0.4 < f["p_over25"] < 0.7
    assert f["match_key"] == live.match_key("E0", "2026-11-08", "Arsenal", "Chelsea")


def test_bst_kickoff():
    csv = b"Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A\nE0,15/08/2026,15:00,Arsenal,Chelsea,1.8,3.8,4.4\n"
    assert live.parse_fixtures(live.read_csv_bytes(csv))[0]["kickoff_utc"] == "2026-08-15T14:00:00+00:00"


def test_seal_detects_tampering():
    rec = live.seal({"match_key": "abc", "predictions": {"market": {"fav": 0.5}}})
    assert live.verify(rec)
    rec["predictions"]["market"]["fav"] = 0.9
    assert not live.verify(rec)


def test_commit_settle_report_roundtrip(tmp_path):
    fx = live.parse_fixtures(live.read_csv_bytes(CSV))
    now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    assert live.commit(fx, now, 4, tmp_path)["committed"] == 1
    assert live.commit(fx, now, 4, tmp_path)["committed"] == 0           # idempotent
    res = live.parse_results(live.read_csv_bytes(
        b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nE0,08/11/2026,Arsenal,Chelsea,2,1\n"))
    assert live.settle(res, datetime(2026, 11, 9, tzinfo=timezone.utc), tmp_path) == 1
    rep = live.report(tmp_path)
    assert rep["settled"] == 1 and rep["integrity"]["hash_ok"] == 1
    assert rep["engines"]["market"]["n"] == 1


def test_late_predictions_do_not_count(tmp_path):
    fx = live.parse_fixtures(live.read_csv_bytes(CSV))
    rec = live.predict_fixture(fx[0], datetime(2026, 11, 6, tzinfo=timezone.utc))
    rec = live.seal({**rec, "committed_at": "2026-11-08T15:30:00+00:00"})   # after kickoff
    (tmp_path / "predictions").mkdir()
    (tmp_path / "predictions" / "x.jsonl").write_text(json.dumps(rec) + "\n")
    live.settle({rec["match_key"]: {"goals_home": 1, "goals_away": 0}}, datetime(2026, 11, 9, tzinfo=timezone.utc), tmp_path)
    rep = live.report(tmp_path)
    assert rep["integrity"]["late"] == 1 and rep["settled"] == 0


def test_results_url_by_league():
    ko = datetime(2026, 11, 8, tzinfo=timezone.utc)
    assert live.results_url("E0", ko).endswith("/mmz4281/2627/E0.csv")
    assert live.results_url("BRA", ko).endswith("/new/BRA.csv")
    assert live.season_code(datetime(2027, 3, 1, tzinfo=timezone.utc)) == "2627"
