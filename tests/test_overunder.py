import numpy as np
import pandas as pd

from astrofoot import live, overunder


def rec(p_over, totals, home_goals=None, away_goals=None, key="k", day="2026-11-04", t="15:00"):
    preds = {e: {"winner": "fav", "goals_fav": g[0], "goals_dog": g[1], "net": 0, "confidence": "low"}
             for e, g in zip(("rao", "chokoisky", "frawley"), totals)}
    preds["market"] = preds["synthesis"] = {"fav": .5, "draw": .3, "dog": .2}
    return {"match_key": key, "p_over25": p_over, "predictions": preds, "kickoff_utc": f"{day}T{t}:00+00:00",
            "committed_at": f"{day}T05:00:00+00:00", "fav_is_home": True}


def test_calibration_stretches_away_from_half_and_view_counts_agreement():
    cal = {"calibration": {"a": 0.0, "b": 1.12}}
    assert abs(overunder.calibrate(0.5, cal) - 0.5) < 1e-9
    assert overunder.calibrate(0.65, cal) > 0.65 and overunder.calibrate(0.35, cal) < 0.35
    assert overunder.calibrate(None, cal) is None
    v = overunder.view(rec(0.62, [(2, 1), (5, 0), (1, 0)]), {"goals_home": 2, "goals_away": 2}, cal)
    assert v["ou_pick"] == "over" and v["ou_agree"] == 2 and v["ou_goals"] == 4 and v["ou_hit"] is True
    u = overunder.view(rec(0.40, [(2, 1), (1, 1), (1, 0)]), {"goals_home": 3, "goals_away": 0}, cal)
    assert u["ou_pick"] == "under" and u["ou_agree"] == 2 and u["ou_hit"] is False
    none = overunder.view(rec(None, [(2, 1)] * 3), None, cal)
    assert none["ou_pick"] is None and none["ou_engine_totals"]["rao"] == 3


def test_engine_rules_match_the_engines():
    win = np.array([1, 1, 1, 0, -1, 1])
    net = np.array([2, 5, 9, 0, -3, 0])
    assert list(overunder.rao_over(win, net)) == [True, False, True, False, True, True]
    assert list(overunder.chok_over(np.array([1, 1, 0, -1]), np.array([6, 8, 0, -12]))) == [False, True, False, True]


def test_top_picks_goals_ranking_and_scoring():
    recs = []
    for i, (p, gh, ga) in enumerate([(0.70, 3, 1), (0.30, 0, 0), (0.55, 1, 0), (None, 2, 2)]):
        r = rec(p, [(2, 1)] * 3, key=f"k{i}")
        res = {"goals_home": gh, "goals_away": ga}
        recs.append({**r, "pre_kickoff": True, "classical_agree": 0, "pick_p": .5, "pick_hit": None,
                     **overunder.view(r, res)})
    tp = live.top_picks(recs, per_day=2, market="goals")
    picks = tp["2026-11-04"]
    assert [p["match_key"] for p in picks] == ["k0", "k1"]          # most probable side first, unpriced left out
    s = live.score_picks(picks, "goals")
    assert s["n"] == 2 and s["hits"] == 2


def test_backtest_runs_on_synthetic_history():
    rng = np.random.default_rng(0)
    n = 3000
    p = rng.uniform(0.3, 0.7, n)
    y = rng.uniform(size=n) < np.clip(0.5 + 1.15 * (p - 0.5), 0, 1)
    m = pd.DataFrame({"season": np.repeat(["2021/22", "2022/23", "2023/24"], n // 3),
                      "kickoff_utc": pd.date_range("2021-08-01", periods=n, freq="6h", tz="UTC").astype(str),
                      "p_over25": p, "goals_home": np.where(y, 2, 1), "goals_away": np.where(y, 1, 0)})
    e = pd.DataFrame({"rao_win": rng.choice([-1, 0, 1], n), "rao_net": rng.integers(-10, 10, n),
                      "chok_win": rng.choice([-1, 0, 1], n), "chok_net": rng.integers(-15, 15, n)})
    r = overunder.backtest(m, e)
    assert r["calibration"]["b"] > 1 and r["top"]["n"] > 0
    assert abs(r["engines"]["rao"]["lift"]) < 4 * r["engines"]["rao"]["se"] + 0.02


def test_team_to_score_probabilities_and_view():
    from astrofoot import teamgoals
    cal = {"calibration": {"a": 0.21, "b": 1.015, "c": -0.011}}
    ph, pa = teamgoals.score_probs(0.70, 0.12, cal)          # strong home favourite
    assert 0.85 < ph < 0.97 and pa < 0.65 and ph > pa
    ph2, pa2 = teamgoals.score_probs(0.15, 0.65, cal)        # strong away favourite
    assert pa2 > ph2
    r = rec(0.6, [(2, 1), (1, 0), (2, 0)])
    r.update({"home": "Home FC", "away": "Away FC", "fav_is_home": False,
              "predictions": {**r["predictions"], "market": {"fav": 0.65, "draw": 0.2, "dog": 0.15}}})
    v = teamgoals.view(r, {"goals_home": 0, "goals_away": 2}, cal)
    assert v["ts_pick"] == "away" and v["ts_team"] == "Away FC" and v["ts_hit"] is True
    assert v["ts_engine_scores"]["rao"] == (1, 2) and v["ts_agree"] == 3


def test_engine_scoring_rules():
    from astrofoot import teamgoals
    win, net = np.array([1, 1, 0, -1]), np.array([2, 6, 0, -9])
    fs, ds = teamgoals.rao_scores(win, net)          # 2–1, 2–0, 1–1, 0–3 (fav first)
    assert list(fs) == [True, True, True, False] and list(ds) == [True, False, True, True]
    fs, ds = teamgoals.chok_scores(np.array([1, 0, -1]), np.array([9, 0, -9]))
    assert list(fs) == [True, True, False] and list(ds) == [False, True, True]
