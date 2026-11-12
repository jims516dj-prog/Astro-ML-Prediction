from datetime import datetime, timezone

from astrofoot import fixtures_oddspapi as op
from astrofoot import live

KO = "2026-11-13T13:00:00+00:00"


def test_national_teams_by_country_code_and_one_side():
    assert live.same_game("Saudi Arabia", "South Korea", KO, "Saudi Arabia", "Korea Republic", KO)
    assert live.same_game("Czech Republic", "Spain", KO, "Czechia", "Spain", KO)
    assert live.same_game("Scotland", "FYR Macedonia", KO, "Scotland", "North Macedonia", KO)
    # a source naming the wrong Congo still lists that one game: Comoros does not play twice at once
    assert live.same_game("Comoros", "Congo DR", KO, "Comoros", "Congo Republic", KO)


def test_different_teams_stay_apart():
    assert not live.same_game("England", "Portugal", KO, "Scotland", "North Macedonia", KO)      # home nations
    assert not live.same_game("Denmark U21", "Netherlands U21", KO, "Denmark", "Netherlands", KO)
    assert not live.same_game("Rosario Central Reserve", "River Plate Reserve", KO, "Rosario Central", "River Plate", KO)
    assert not live.same_game("Nacional", "Penarol", KO, "Nacional", "Porto", KO)                  # two clubs called Nacional
    assert live.same_game("Rosario Central Res.", "CA River Plate (Arg) Reserve", KO, "Rosario Central Reserve",
                          "River Plate Res.", KO)


def test_oddspapi_adds_the_age_group():
    f = {"tournamentName": "U21 Friendly Games", "categoryName": "International Youth"}
    assert op.with_age("England", f) == "England U21" and op.with_age("England U21", f) == "England U21"
    assert op.with_age("England", {"tournamentName": "Int. Friendly Games", "categoryName": "International"}) == "England"


def rec(key, home, away, div, league, at, ko=KO):
    return live.seal({"match_key": key, "home": home, "away": away, "division": div, "league": league,
                      "kickoff_utc": ko, "committed_at": at})


def test_withdraw_duplicates_keeps_the_earlier_and_drops_misnamed_youth(tmp_path):
    live._append(tmp_path / "predictions" / "2026-11-12.jsonl", [
        rec("a", "Comoros", "Congo DR", "X:caf.nations_qual", "Africa Cup of Nations Qualifying", "2026-11-12T07:00:00+00:00"),
        rec("b", "Comoros", "Congo Republic", "O:1848", "International: AFCON Qualification", "2026-11-12T11:00:00+00:00"),
        rec("c", "Finland", "Ireland", "O:26", "International Youth: U21 Qualification", "2026-11-12T11:00:00+00:00"),
        rec("d", "Finland U21", "Republic of Ireland U21", "X:uefa.euro_u21_qual", "U21 qualifying", "2026-11-12T12:00:00+00:00"),
    ])
    now = datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc)
    notes = live.withdraw_duplicates(now, tmp_path)
    res = live.read_results(tmp_path)
    assert set(res) == {"b", "c"} and all(v["reason"].startswith("withdrawn before kickoff") for v in res.values())
    assert len(notes) == 2 and live.withdraw_duplicates(now, tmp_path) == []
    # and a new fixture for the same game from a third source is not sealed again
    r = live.commit([{"match_key": "e", "division": "A:5", "home": "Comoros", "away": "Congo", "kickoff_utc": KO,
                      "odds": {"home": 1.8, "draw": 3.1, "away": 4.6}}], now, 4, tmp_path)
    assert r["committed"] == 0 and "already forecast" in r["skipped"][-1]
