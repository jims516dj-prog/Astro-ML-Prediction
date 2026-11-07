from datetime import datetime, timezone

import pandas as pd

from astrofoot import form


def rec(home, away, ko, fav_is_home=True, winners=("fav", "fav", "dog"), result=None):
    return {"match_key": "k", "home": home, "away": away, "kickoff_utc": ko, "fav_is_home": fav_is_home,
            "division": "E0", "result": result,
            "predictions": {"market": {"fav": 0.5, "draw": 0.28, "dog": 0.22},
                            **{e: {"winner": w} for e, w in zip(("rao", "chokoisky", "frawley"), winners)}}}


def hist(games):
    out = {}
    for ko, h, a, gh, ga in games:
        t = pd.Timestamp(ko, tz="UTC")
        out.setdefault(h, []).append((t, "H", a, gh, ga, "E0"))
        out.setdefault(a, []).append((t, "A", h, ga, gh, "E0"))
    for v in out.values():
        v.sort(key=lambda x: x[0], reverse=True)
    return out


def test_backed_side_needs_two_engines_on_the_same_team():
    assert form.backed_side(rec("A", "B", "2026-11-09T15:00:00+00:00"))[:2] == ("home", 2)
    assert form.backed_side(rec("A", "B", "2026-11-09T15:00:00+00:00", fav_is_home=False))[:2] == ("away", 2)
    assert form.backed_side(rec("A", "B", "2026-11-09T15:00:00+00:00", winners=("dog", "dog", "dog")))[:2] == ("away", 3)
    side, n, _ = form.backed_side(rec("A", "B", "2026-11-09T15:00:00+00:00", winners=("fav", "draw", "dog")))
    assert side is None and n == 1


def test_windows_use_venue_overall_h2h_and_only_the_past():
    games = [(f"2026-10-{d:02d}T15:00:00", "A", f"X{d}", 2, 1) for d in range(1, 8)]          # A at home 7 times
    games += [(f"2026-09-{d:02d}T15:00:00", f"Y{d}", "A", 0, 1) for d in range(1, 4)]          # A away 3 times
    games += [("2025-12-01T15:00:00", "A", "B", 3, 0), ("2025-05-01T15:00:00", "B", "A", 1, 1),
              ("2024-12-01T15:00:00", "A", "B", 0, 0), ("2024-01-01T15:00:00", "B", "A", 2, 2)]
    games += [(f"2026-10-{d:02d}T18:00:00", f"Z{d}", "B", 2, 2) for d in range(1, 6)]          # B away, concedes 2
    games += [("2026-11-20T15:00:00", "A", "Q", 9, 0)]                                          # after kickoff: ignored
    a = form.analyse(rec("A", "B", "2026-11-09T15:00:00+00:00", result={"goals_home": 1, "goals_away": 0}), hist(games))
    assert a["qualifies"] and a["team"] == "A" and a["venue_word"] == "home" and a["role"] == "favourite"
    assert a["team_venue"]["n"] == 5 and a["team_venue"]["gf"] == 2.0 and a["team_venue"]["games"][0]["date"] == "2026-10-07"
    assert a["team_all"]["n"] == 5 and a["h2h"]["n"] == 3 and [g["gf"] for g in a["h2h"]["games"]] == [3, 1, 0]
    assert a["opp_venue"]["n"] == 5 and a["opp_venue"]["ga"] == 2.0
    assert 0 < a["p_form"] < 1 and a["p_form2"] < a["p_form"] and a["scored_hit"] is True
    lam = form.form_lambda(2.0, 2.0, 4 / 3, 2.0, 2.0)
    assert abs(a["lam_form"] - lam) < 1e-9


def test_refresh_recent_writes_both_seasons(tmp_path):
    now = datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc)
    files = {"2627": pd.DataFrame({"Div": ["E0", "E0"], "Date": ["01/11/2026", "08/11/2026"], "Time": ["15:00", "15:00"],
                                   "HomeTeam": ["A", "C"], "AwayTeam": ["B", "D"], "FTHG": [2, None], "FTAG": [1, None]}),
             "2526": pd.DataFrame({"Div": ["E0"], "Date": ["10/05/2026"], "Time": ["15:00"], "HomeTeam": ["B"],
                                   "AwayTeam": ["A"], "FTHG": [0], "FTAG": [0]})}
    path = tmp_path / "recent.csv"
    n = form.refresh_recent(now, lambda url: files[url.split("/")[-2]], ["E0"], path, log=lambda *a: None)
    out = pd.read_csv(path)
    assert n == 2 and set(out.home) == {"A", "B"}                                       # unplayed game left out
    assert form.refresh_recent(now, lambda url: 1 / 0, ["E0"], path, log=lambda *a: None) == -1   # fresh: skipped
    later = datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)                                       # a day on: refreshed
    assert form.refresh_recent(later, lambda url: files[url.split("/")[-2]], ["E0"], path, log=lambda *a: None) == 2


def test_extra_league_file_names():
    from astrofoot import live
    when = datetime(2026, 11, 7, tzinfo=timezone.utc)
    assert live.results_url("DEN", when).endswith("/new/DNK.csv") and live.results_url("JAP", when).endswith("/new/JPN.csv")
    assert live.results_url("SUI", when).endswith("/new/SWZ.csv")
    assert live.results_url("BRA", when).endswith("/new/BRA.csv") and live.results_url("E0", when).endswith("/2627/E0.csv")
