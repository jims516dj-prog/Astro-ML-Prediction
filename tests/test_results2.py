from datetime import datetime, timezone

from astrofoot import live, results2


def api_match(code, utc, home, away, gh, ga, short_h=None, short_a=None, status="FINISHED"):
    return {"competition": {"code": code}, "utcDate": utc, "status": status,
            "homeTeam": {"name": home, "shortName": short_h or home, "tla": ""},
            "awayTeam": {"name": away, "shortName": short_a or away, "tla": ""},
            "score": {"fullTime": {"home": gh, "away": ga}}}


def rec(div, ko, home, away, key):
    return {"division": div, "kickoff_utc": ko, "home": home, "away": away, "match_key": key}


MATCHES = [
    api_match("PL", "2026-11-02T20:00:00Z", "Newcastle United FC", "Everton FC", 2, 1, "Newcastle", "Everton"),
    api_match("SA", "2026-11-02T19:45:00Z", "Atalanta BC", "Parma Calcio 1913", 3, 0, "Atalanta", "Parma"),
    api_match("SA", "2026-11-02T19:45:00Z", "FC Internazionale Milano", "Hellas Verona FC", 1, 1, "Inter", "Verona"),
    api_match("PD", "2026-11-02T20:00:00Z", "RC Deportivo La Coruña", "CA Osasuna", 0, 0, "La Coruña", "Osasuna"),
    api_match("PPL", "2026-11-02T20:15:00Z", "Sporting Clube de Portugal", "Gil Vicente FC", 4, 1, "Sporting CP", "Gil Vicente"),
    api_match("PL", "2026-11-03T20:00:00Z", "Wolverhampton Wanderers FC", "Nottingham Forest FC", 0, 2, "Wolves", "Nottingham"),
    api_match("PL", "2026-11-04T20:00:00Z", "Arsenal FC", "Chelsea FC", 1, 0, status="IN_PLAY"),
]


def test_names_from_both_sources_are_paired_correctly():
    pending = [rec("E0", "2026-11-02T20:00:00+00:00", "Newcastle", "Everton", "k1"),
               rec("I1", "2026-11-02T19:45:00+00:00", "Atalanta", "Parma", "k2"),        # two SA games at 19:45
               rec("I1", "2026-11-02T19:45:00+00:00", "Inter", "Verona", "k3"),
               rec("SP1", "2026-11-02T20:00:00+00:00", "La Coruna", "Osasuna", "k4"),
               rec("P1", "2026-11-02T20:15:00+00:00", "Sp Lisbon", "Gil Vicente", "k5"),
               rec("E0", "2026-11-03T20:00:00+00:00", "Wolves", "Nott'm Forest", "k6"),
               rec("E0", "2026-11-04T20:00:00+00:00", "Arsenal", "Chelsea", "k7")]        # not finished yet
    found, notes = results2.match_results(pending, MATCHES)
    assert {k: (v["goals_home"], v["goals_away"]) for k, v in found.items()} == {
        "k1": (2, 1), "k2": (3, 0), "k3": (1, 1), "k4": (0, 0), "k5": (4, 1), "k6": (0, 2)}
    assert all(v["source"] == "football-data.org" for v in found.values())


def test_uncertain_pairs_are_left_pending():
    pending = [rec("I1", "2026-11-02T19:45:00+00:00", "Lazio", "Roma", "kx")]           # not among SA 19:45 games
    found, notes = results2.match_results(pending, MATCHES)
    assert found == {} and notes and "no confident match" in notes[0]
    assert results2.match_results([rec("E2", "2026-11-02T20:00:00+00:00", "Newcastle", "Everton", "ky")],
                                  MATCHES)[0] == {}                                     # league not covered


def test_extra_time_uses_regular_time():
    m = api_match("PL", "2026-11-02T20:00:00Z", "Newcastle United FC", "Everton FC", 3, 2)
    m["score"]["regularTime"] = {"home": 2, "away": 2}
    found, _ = results2.match_results([rec("E0", "2026-11-02T20:00:00+00:00", "Newcastle", "Everton", "k")], [m])
    assert (found["k"]["goals_home"], found["k"]["goals_away"]) == (2, 2)


def test_primary_source_confirms_or_corrects_a_secondary_result(tmp_path):
    (tmp_path / "predictions").mkdir()
    for k in ("a", "b"):
        r = live.seal({"match_key": k, "kickoff_utc": "2026-11-02T20:00:00+00:00", "division": "E0",
                       "committed_at": "2026-11-01T00:00:00+00:00", "fav_is_home": True,
                       "predictions": {"market": {"fav": .5, "draw": .3, "dog": .2}}})
        with (tmp_path / "predictions" / "d.jsonl").open("a") as fh:
            fh.write(live._canonical(r) + "\n")
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    fast = {"a": {"goals_home": 2, "goals_away": 1, "source": "football-data.org"},
            "b": {"goals_home": 1, "goals_away": 1, "source": "football-data.org"}}
    assert live.settle(fast, now, tmp_path) == 2
    assert live.needed_result_urls(tmp_path, now)                      # unconfirmed: keep checking the primary
    primary = {"a": {"goals_home": 2, "goals_away": 1, "source": live.PRIMARY},
               "b": {"goals_home": 2, "goals_away": 1, "source": live.PRIMARY}}
    assert live.settle(primary, now, tmp_path) == 2
    res = live.read_results(tmp_path)
    assert "confirms" in res["a"] and res["b"]["corrects"]["goals_home"] == 1 and res["b"]["goals_home"] == 2
    assert live.needed_result_urls(tmp_path, now) == set()             # all confirmed by the primary
    assert live.report(tmp_path)["settled"] == 2                      # still two matches, not four
