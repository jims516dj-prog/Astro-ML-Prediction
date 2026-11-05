import json

from astrofoot import live, merged


def analysis(fav_is_a=True):
    v = {"winner": "fav", "goals_fav": 2, "goals_dog": 1, "net": 3, "confidence": "low"}
    return {"fav": "Alpha" if fav_is_a else "Beta", "dog": "Beta" if fav_is_a else "Alpha", "fav_is_a": fav_is_a,
            "market": {"p_fav": 0.55, "p_draw": 0.25, "p_dog": 0.20},
            "synthesis": {"probabilities": {"fav": 0.55, "draw": 0.25, "dog": 0.20}},
            "verdicts": {"rao": v, "chokoisky": v, "frawley": v}, "engine4": None, "inputs": {"p_over25": 0.55}}


def row(i, a="Alpha", b="Beta", ko="2026-11-09T15:00:00+00:00", **kw):
    return {"id": i, "team_a": a, "team_b": b, "home_side": "A", "kickoff_utc": ko, "created_at": "2026-11-05T10:00:00+00:00",
            "odds_a": 1.8, "odds_d": 3.6, "odds_b": 4.4, "analysis_json": json.dumps(analysis()), "status": "pending",
            "score_a": None, "score_b": None, "post_hoc": 0, **kw}


def live_rec(key, home, away, ko):
    r = {"match_key": key, "division": "E0", "home": home, "away": away, "kickoff_utc": ko, "fav_is_home": True,
         "favourite": home, "underdog": away, "committed_at": "2026-11-05T05:00:00+00:00", "p_over25": None,
         "predictions": {"market": {"fav": .5, "draw": .3, "dog": .2}, "synthesis": {"fav": .5, "draw": .3, "dog": .2},
                         **{e: {"winner": "fav", "goals_fav": 1, "goals_dog": 0} for e in ("rao", "chokoisky", "frawley")}}}
    return live.join(r, None)


def test_same_game_rules():
    ko = "2026-11-09T15:00:00+00:00"
    assert merged.same_game("Man United", "Wolves", ko, "Manchester United", "Wolverhampton", "2026-11-09T17:00:00+00:00")
    assert merged.same_game("Alpha", "Beta", ko, "Beta", "Alpha", ko)                 # neutral venue, swapped
    assert not merged.same_game("Alpha", "Beta", ko, "Alpha", "Beta", "2026-11-12T15:00:00+00:00")
    assert not merged.same_game("Alpha", "Beta", ko, "Alpha", "Gamma", ko)


def test_manual_games_join_the_list_once_and_live_wins():
    lv = [live_rec("L1", "Alpha", "Beta", "2026-11-09T15:00:00+00:00")]
    rows = [row("m1"), row("m2", "Gamma", "Delta"), row("m3", "Gamma FC", "Delta", ko="2026-11-09T16:00:00+00:00")]
    out = merged.all_records(rows, lv)
    keys = [r["match_key"] for r in out]
    assert keys.count("L1") == 1 and "m-m1" not in keys                  # folded into the live forecast
    assert out[keys.index("L1")]["also"] == ["/match/m1"]
    gamma = [r for r in out if r["origin"] == "manual"]
    assert len(gamma) == 1 and gamma[0]["match_key"] == "m-m2"         # two manual copies shown once
    g = gamma[0]
    assert g["url"] == "/match/m2" and g["status"] == "pending" and g["pre_kickoff"] and g["ou_pick"] is not None


def test_manual_results_void_and_post_hoc():
    done = merged.manual_records([row("m4", score_a=0, score_b=2, status="completed")])[0]
    assert done["status"] == "settled" and done["outcome"] == "dog" and done["pick_hit"] is False
    void = merged.manual_records([row("m5", status="abandoned")])[0]
    assert void["status"] == "void"
    late = merged.manual_records([row("m6", post_hoc=1)])[0]
    assert not late["pre_kickoff"]                                       # never counted as a forecast


def test_find_duplicate():
    preds = [{"match_key": "L1", "home": "Alpha", "away": "Beta", "kickoff_utc": "2026-11-09T15:00:00+00:00"}]
    assert merged.find_duplicate("Alpha", "Beta", "2026-11-09T14:00:00+00:00", [], preds) == ("live", "L1")
    assert merged.find_duplicate("Gamma", "Delta", "2026-11-09T15:00:00+00:00", [row("m2", "Gamma", "Delta")], []) == ("manual", "m2")
    assert merged.find_duplicate("Gamma", "Delta", "2026-11-20T15:00:00+00:00", [row("m2", "Gamma", "Delta")], []) is None


def test_summary_picks_most_likely_outcome_per_game():
    r = live_rec("S1", "Alpha", "Beta", "2026-11-09T15:00:00+00:00")
    opts = live.outcome_options(r)
    assert [o["p"] for o in opts] == sorted((o["p"] for o in opts), reverse=True)
    assert {o["market"] for o in opts} >= {"result", "dc", "o15", "score", "btts"}
    live.add_summary([r])
    assert r["sum_pick_p"] == opts[0]["p"] and r["sum_market"] == opts[0]["market"]
    live.add_summary([r], ["result", "btts"])
    assert r["sum_market"] in ("result", "btts")
    assert r["sum_pick_p"] == max(o["p"] for o in opts if o["market"] in ("result", "btts"))
    picks = live.top_picks([r], market="summary")
    assert picks["2026-11-09"][0]["match_key"] == "S1"
