import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from astrofoot import live
from astrofoot.config import RAW

needs_venues = pytest.mark.skipif(not (RAW / "stadiums.csv").exists(),
                                  reason="venue tables missing: run python scripts/fetch_data.py --live")

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


@needs_venues
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


@needs_venues
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


def _rec(day, home, p_fav, outcome=None, committed="2026-11-01T00:00:00+00:00"):
    r = {"kickoff_utc": f"{day}T15:00:00+00:00", "committed_at": committed, "home": home, "away": "X",
         "predictions": {"market": {"fav": p_fav, "draw": (1 - p_fav) / 2, "dog": (1 - p_fav) / 2},
                         "rao": {"winner": "fav"}, "chokoisky": {"winner": "dog"}, "frawley": {"winner": "fav"}}}
    return {**r, "pre_kickoff": committed < r["kickoff_utc"], "pick": "fav", "pick_p": p_fav, "classical_agree": 2,
            "outcome": outcome, "pick_hit": None if outcome is None else outcome == "fav"}


def test_top_picks_are_capped_per_day_and_ranked_by_probability():
    recs = [_rec("2026-11-02", f"T{i}", 0.30 + i / 100) for i in range(15)] + [_rec("2026-11-03", "Solo", 0.5)]
    tp = live.top_picks(recs, per_day=10)
    assert len(tp["2026-11-02"]) == 10 and len(tp["2026-11-03"]) == 1
    probs = [r["pick_p"] for r in tp["2026-11-02"]]
    assert probs == sorted(probs, reverse=True) and probs[0] == 0.44


def test_top_picks_ignore_late_records_and_score_honestly():
    late = _rec("2026-11-02", "Late", 0.99, committed="2026-11-02T16:00:00+00:00")
    assert live.top_picks([late]) == {}                  # committed after kickoff: never a pick
    s = live.score_picks([_rec("d", "A", 0.8, "fav"), _rec("d", "B", 0.6, "dog"), _rec("d", "C", 0.7)])
    assert s["n"] == 2 and s["hits"] == 1 and abs(s["expected"] - 0.7) < 1e-9
