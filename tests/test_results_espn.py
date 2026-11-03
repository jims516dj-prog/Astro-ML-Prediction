from astrofoot import results_espn


def ev(home, away, gh, ga, utc, status="STATUS_FULL_TIME", short=None):
    team = lambda n, s: {"displayName": n, "shortDisplayName": s or n, "name": n, "abbreviation": n[:3].upper()}
    return {"date": utc, "status": {"type": {"name": status, "completed": True}},
            "competitions": [{"date": utc, "competitors": [
                {"homeAway": "home", "score": str(gh), "team": team(home, short)},
                {"homeAway": "away", "score": str(ga), "team": team(away, None)}]}]}


def rec(key, div, home, away, ko):
    return {"match_key": key, "division": div, "home": home, "away": away, "kickoff_utc": ko}


def test_pairs_lower_leagues_and_skips_extra_time():
    events = {
        "T1": [ev("Gençlerbirliği", "Alanyaspor", 1, 1, "2026-11-02T17:00Z"),
               ev("Galatasaray", "Fenerbahçe", 3, 0, "2026-11-02T17:00Z")],
        "SP2": [ev("CD Tenerife", "FC Andorra", 2, 0, "2026-11-01T20:00Z"),
                ev("Real Valladolid", "CD Leganés", 1, 2, "2026-11-02T17:30Z"),
                ev("RCD Mallorca", "Cádiz CF", 0, 0, "2026-11-02T20:00Z", status="STATUS_FINAL_PEN")],
        "SWE": [ev("IK Sirius", "Halmstads BK", 2, 1, "2026-11-03T18:00Z")],
    }
    pending = [rec("a", "T1", "Genclerbirligi", "Alanyaspor", "2026-11-02T17:00:00+00:00"),
               rec("b", "SP2", "Tenerife", "Andorra", "2026-11-01T20:00:00+00:00"),
               rec("c", "SP2", "Valladolid", "Leganes", "2026-11-02T17:30:00+00:00"),
               rec("d", "SP2", "Mallorca", "Cadiz", "2026-11-02T20:00:00+00:00"),
               rec("e", "SWE", "Sirius", "Halmstad", "2026-11-03T18:00:00+00:00"),
               rec("f", "XYZ", "A", "B", "2026-11-03T18:00:00+00:00")]
    found, notes, counts = results_espn.match_results(pending, fetcher=lambda d, a, b: events.get(d, []))
    assert found["a"] == {"goals_home": 1, "goals_away": 1, "source": "espn.com"}
    assert found["b"]["goals_home"] == 2 and found["c"]["goals_away"] == 2
    assert found["e"]["goals_home"] == 2
    assert "d" not in found and "f" not in found        # penalties, unknown league
    assert counts == {"SP2": 2, "SWE": 1, "T1": 2}


def test_feed_failure_is_a_note_not_a_crash():
    def boom(*a):
        raise OSError("down")
    found, notes, _ = results_espn.match_results(
        [rec("a", "G1", "Kalamata", "Iraklis", "2026-11-02T17:30:00+00:00")], fetcher=boom)
    assert found == {} and "unavailable" in notes[0]
