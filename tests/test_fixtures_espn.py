from datetime import datetime, timezone

from astrofoot import fixtures_espn, live

NOW = datetime(2026, 11, 9, 6, 0, tzinfo=timezone.utc)


def ev(home, away, when, ml=(-150, 260, 400), total=("o2.5", "+100", "-120"), venue=("Estadio X", "Gijón", "Spain")):
    odds = {"provider": {"name": "DraftKings"}, "homeTeamOdds": {"moneyLine": ml[0]}, "drawOdds": {"moneyLine": ml[1]},
            "awayTeamOdds": {"moneyLine": ml[2]}} if ml else {}
    if total and ml:
        odds["total"] = {"over": {"close": {"line": total[0], "odds": total[1]}},
                         "under": {"close": {"line": "u2.5", "odds": total[2]}}}
    return {"date": when, "status": {"type": {"state": "pre"}},
            "competitions": [{"date": when, "odds": [odds] if ml else [],
                              "venue": {"fullName": venue[0], "address": {"city": venue[1], "country": venue[2]}},
                              "competitors": [{"homeAway": "home", "team": {"displayName": home}},
                                              {"homeAway": "away", "team": {"displayName": away}}]}]}


def local_date(ko):
    return ko.astimezone(timezone.utc).strftime("%Y-%m-%d")


def test_moneyline_block_and_null_odds():
    e = ev("A", "B", "2026-11-09T19:00Z")
    o = e["competitions"][0]["odds"][0]
    for k in ("homeTeamOdds", "awayTeamOdds"):
        o.pop(k)
    o["moneyline"] = {"home": {"open": {"odds": "-210"}, "close": {"odds": "-185"}},
                      "away": {"close": {"odds": "+390"}}, "draw": {"close": {"odds": "+310"}}}
    g = fixtures_espn.parse_event(e)
    assert abs(g["odds"][0] - (1 + 100 / 185)) < 1e-9 and g["odds"][2] == 4.9 and g["odds"][1] == 4.1
    e["competitions"][0]["odds"] = [None]
    assert fixtures_espn.parse_event(e) is None


def test_american_odds_and_parse():
    assert abs(fixtures_espn.american_to_decimal(-150) - 1.6667) < 1e-3
    assert fixtures_espn.american_to_decimal("+260") == 3.6 and fixtures_espn.american_to_decimal(0) is None
    g = fixtures_espn.parse_event(ev("A", "B", "2026-11-09T19:00Z"))
    assert g["odds"][1] == 3.6 and abs(g["p_over25"] - (1 / 2.0) / (1 / 2.0 + 1 / (1 + 100 / 120))) < 1e-9
    assert fixtures_espn.parse_event(ev("A", "B", "2026-11-09T19:00Z", ml=None)) is None          # no odds: unusable


def test_extra_fixtures_leagues_cups_and_dedupe():
    feeds = {"esp.2": [ev("Sporting Gijón", "Real Valladolid", "2026-11-09T19:00Z"),
                       ev("Unknown CF", "Real Valladolid", "2026-11-09T21:00Z"),
                       ev("Burgos CF", "Castellón", "2026-11-09T17:00Z")],
             "esp.copa_del_rey": [ev("CD Lugo", "Sevilla", "2026-11-09T20:00Z", venue=("Anxo Carro", "Lugo", "Spain"))]}
    fetch = lambda slug, day: feeds.get(slug, []) if day == NOW.date() else []          # noqa: E731
    primary = [{"match_key": "p1", "division": "SP2", "home": "Burgos", "away": "Castellon",
                "kickoff_utc": "2026-11-09T17:00:00+00:00"}]
    known = {"SP2": {"Sp Gijon", "Valladolid", "Burgos", "Castellon"}}
    grounds = []

    def venue_of(team, division=None, hint=None):
        grounds.append((team, division, hint["name"]))
        return (43.0, -7.5, "wikipedia: " + hint["name"])
    out = fixtures_espn.extra_fixtures(primary, NOW, 4, live.match_key, local_date, [], lambda d: known.get(d, set()),
                                       {"Sevilla"}, venue_of, fetch=fetch, log=lambda *a: None)
    got = {(f["division"], f["home"], f["away"]) for f in out}
    assert ("SP2", "Sp Gijon", "Valladolid") in got                    # our league: football-data.co.uk names
    assert not any(f["home"] == "Unknown CF" for f in out)              # name not recognised: skipped
    assert not any(f["home"].startswith("Burgos") for f in out)         # the primary already lists it
    cup = next(f for f in out if f["division"] == "CDR")
    assert (cup["home"], cup["away"]) == ("CD Lugo", "Sevilla") and cup["venue_source"] == "wikipedia: Anxo Carro"
    assert grounds == [("CD Lugo", "CDR", "Anxo Carro")] and cup["odds_source"] == "espn.com DraftKings"
    gij = next(f for f in out if f["home"] == "Sp Gijon")
    assert "venue_lat" not in gij and gij["p_over25"] is not None
