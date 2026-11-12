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


def test_discovery_remembers_competitions_with_odds(tmp_path, monkeypatch):
    path = tmp_path / "comps.json"
    pages = {fixtures_espn.CORE: {"items": [{"$ref": "http://x/leagues/bol.1?lang=en"}, {"$ref": "http://x/leagues/ven.1?"},
                                             {"$ref": "http://x/leagues/bra.w.1?"}, {"$ref": "http://x/leagues/esp.u19?"}]}}

    def get(url):
        if url in pages:
            return pages[url]
        slug = url.split("/soccer/")[1].split("/")[0]
        if slug == "bol.1" and url.endswith(NOW.strftime("%Y%m%d")):
            return {"leagues": [{"name": "Bolivian Liga"}], "events": [ev("Bolívar", "The Strongest", "2026-11-09T23:00Z")]}
        return {"leagues": [{"name": slug}], "events": [ev("A", "B", "2026-11-09T23:00Z", ml=None)]}
    assert fixtures_espn.discover(NOW, path, get=get, log=lambda *a: None) == 1
    import json
    assert json.loads(path.read_text())["competitions"] == {"bol.1": "Bolivian Liga"}       # women's/youth not scanned
    assert fixtures_espn.discover(NOW, path, get=get, log=lambda *a: None) == -1             # once a day
    monkeypatch.setattr(fixtures_espn, "COMP_FILE", path)
    fixtures_espn._comps.cache_clear()
    codes = dict(fixtures_espn.discovered_slugs())
    assert codes["X:bol.1"] == "bol.1" and codes["X:ven.1"] == "ven.1"                       # remembered + seed


def test_discovered_competitions_are_secondary_and_named(monkeypatch, tmp_path):
    from astrofoot import dataset, results_espn
    assert "X:bol.1" in dataset.NO_PRIMARY and "E0" not in dataset.NO_PRIMARY and "UCL" in dataset.NO_PRIMARY
    assert results_espn.slug_of("X:bol.1") == "bol.1" and results_espn.slug_of("E0") == "eng.1"
    assert dataset.league_name("X:ven.1") == "Venezuelan Primera División" and dataset.league_name("E0").startswith("England")
    feeds = {"bol.1": [ev("Bolívar", "The Strongest", "2026-11-09T23:00Z", venue=("Hernando Siles", "La Paz", "Bolivia")),
                       ev("Bolívar U20", "Always Ready U20", "2026-11-09T18:00Z")]}
    fetch = lambda slug, day: feeds.get(slug, []) if day == NOW.date() else []                   # noqa: E731
    out = fixtures_espn.extra_fixtures([], NOW, 4, live.match_key, local_date, [], lambda d: set(), set(),
                                       lambda t, **kw: (-16.5, -68.1, "wikipedia: " + kw["hint"]["name"]),
                                       fetch=fetch, log=lambda *a: None)
    # youth sides are included under their own names (never the senior team's)
    assert sorted((f["division"], f["home"], f["away"]) for f in out) == [("X:bol.1", "Bolívar", "The Strongest"),
                                                                         ("X:bol.1", "Bolívar U20", "Always Ready U20")]


def test_efl_trophy_skips_academy_sides():
    feeds = {"eng.trophy": [ev("Leicester City", "Walsall", "2026-11-09T19:00Z"),
                            ev("Barnet", "Leyton Orient", "2026-11-09T19:00Z")]}
    fetch = lambda slug, day: feeds.get(slug, []) if day == NOW.date() else []                   # noqa: E731
    known = {"E1": {"Leicester"}, "E0": {"Arsenal"}}
    out = fixtures_espn.extra_fixtures([], NOW, 4, live.match_key, local_date, [], lambda d: known.get(d, set()),
                                       set(), lambda t, **kw: (51.6, -0.29, "x"), fetch=fetch, log=lambda *a: None)
    assert [(f["home"], f["away"]) for f in out] == [("Barnet", "Leyton Orient")]


def test_distance():
    from astrofoot import venues
    assert 15 < venues.km((51.389, 0.017), (51.524, -0.031)) < 17          # Hayes Lane → Mile End


def test_womens_competitions_never_discovered_or_forecast(tmp_path, monkeypatch):
    import json
    path = tmp_path / "comps.json"
    path.write_text(json.dumps({"generated_at": "2026-11-01T00:00:00+00:00",
                                "competitions": {"uefa.wchampions": "UEFA Women's Champions League", "bol.1": "Bolivian"}}))
    monkeypatch.setattr(fixtures_espn, "COMP_FILE", path)
    fixtures_espn._comps.cache_clear()
    names = fixtures_espn.discovered_names()
    assert "uefa.wchampions" not in names and "bol.1" in names            # an old remembered entry is dropped
    for slug, name in (("uefa.wchampions", "UEFA Women's Champions League"), ("ger.w.1", "Frauen-Bundesliga"),
                       ("mex.w.1", "Liga MX Femenil"), ("usa.nwsl", "NWSL")):
        assert fixtures_espn.NOT_MEN.search(slug) or fixtures_espn.NOT_MEN.search(name)
    for slug, name in (("wal.1", "Welsh Premier League"), ("uefa.champions", "UEFA Champions League")):
        assert not (fixtures_espn.NOT_MEN.search(slug) or fixtures_espn.NOT_MEN.search(name))



def test_youth_names_never_map_to_senior_names():
    assert fixtures_espn.same_age("Liverpool U21", "Liverpool") is None
    assert fixtures_espn.same_age("England U21", "England U21") == "England U21"
    assert fixtures_espn.same_age("Arsenal", "Arsenal") == "Arsenal" and fixtures_espn.same_age("Arsenal", None) is None
    assert fixtures_espn.YOUTH_NAME.search("Spain Sub-20") and fixtures_espn.YOUTH_NAME.search("Italy Under-19")
    assert not fixtures_espn.NOT_MEN.search("uefa.euro_u21_qual") and fixtures_espn.NOT_MEN.search("eng.w.1")
