import importlib.util
import json
from datetime import datetime, timezone

from astrofoot import dataset, fixtures_espn, form, live, results_espn

NOW = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)


def ev(home, away, when, venue=("Kingsmeadow", "Kingston upon Thames", "England")):
    return {"date": when, "status": {"type": {"state": "pre"}},
            "competitions": [{"date": when, "odds": [{"provider": {"name": "DraftKings"},
                              "moneyline": {"home": {"close": {"odds": "+250"}}, "draw": {"close": {"odds": "+260"}},
                                            "away": {"close": {"odds": "-110"}}}}],
                              "venue": {"fullName": venue[0], "address": {"city": venue[1], "country": venue[2]}},
                              "competitors": [{"homeAway": "home", "team": {"displayName": home}},
                                              {"homeAway": "away", "team": {"displayName": away}}]}]}


def test_women_codes_are_separate_secondary_competitions():
    assert "W:eng.w.1" in dataset.NO_PRIMARY and results_espn.slug_of("W:eng.w.1") == "eng.w.1"
    assert dataset.league_name("W:uefa.wchampions") == "UEFA Women's Champions League"
    assert all(code.startswith("W:") for code, _ in fixtures_espn.women_slugs())
    assert not any(slug.startswith("uefa.wch") for _, slug in fixtures_espn.discovered_slugs())   # never in the men's


def test_women_fixtures_keep_women_drop_youth_and_use_the_named_venue():
    feeds = {"eng.w.1": [ev("Chelsea", "Arsenal", "2026-11-10T19:00Z"), ev("Chelsea U21", "Arsenal U21", "2026-11-10T13:00Z")]}
    fetch = lambda slug, day: feeds.get(slug, []) if day == NOW.date() else []          # noqa: E731
    seen = []

    def venue_of(team, division=None, hint=None):
        seen.append(hint["name"])
        return (51.405, -0.281, "wikipedia: " + hint["name"])
    out = fixtures_espn.extra_fixtures([], NOW, 4, live.match_key, lambda ko: ko.strftime("%Y-%m-%d"), [],
                                       lambda d: set(), set(), venue_of, fetch=fetch, log=lambda *a: None,
                                       competitions=[("W:eng.w.1", "eng.w.1")], women=True)
    assert [(f["division"], f["home"], f["away"]) for f in out] == [("W:eng.w.1", "Chelsea", "Arsenal")]
    assert seen == ["Kingsmeadow"] and out[0]["venue_source"] == "wikipedia: Kingsmeadow"


def test_womens_discovery_reads_names(tmp_path):
    pages = {fixtures_espn.CORE: {"items": [{"$ref": "x/leagues/uefa.wchampions?"}, {"$ref": "x/leagues/eng.1?"},
                                             {"$ref": "x/leagues/usa.ncaa.w.1?"}]}}

    def get(url):
        if url in pages:
            return pages[url]
        slug = url.split("/soccer/")[1].split("/")[0]
        name = {"uefa.wchampions": "UEFA Women's Champions League", "eng.1": "English Premier League",
                "usa.ncaa.w.1": "NCAA Women's Soccer"}[slug]
        return {"leagues": [{"name": name}], "events": [ev("A", "B", "2026-11-10T19:00Z")]}
    path = tmp_path / "w.json"
    assert fixtures_espn.discover(NOW, path, get=get, log=lambda *a: None, women=True) == 1
    assert json.loads(path.read_text())["competitions"] == {"uefa.wchampions": "UEFA Women's Champions League"}


def test_women_form_history_never_uses_the_mens_corpus():
    rec = {"kickoff_utc": "2026-11-01T15:00:00+00:00", "home": "Chelsea", "away": "Arsenal", "division": "W:eng.w.1",
           "result": {"goals_home": 2, "goals_away": 2}}
    h = form.history([rec], men=False)
    assert set(h) == {"Chelsea", "Arsenal"} and len(h["Chelsea"]) == 1


def test_women_grounds_use_only_the_named_venue(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("live_script", "scripts/live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m.venues, "wikipedia", lambda q: (51.405, -0.281, q) if q == "Kingsmeadow" else None)
    monkeypatch.setattr(m.geo, "city_lookup", lambda country, city: None)
    g = m.EuropeanGrounds(tmp_path, [], cache_name="venues.json", hint_only=True)
    assert g("Chelsea") is None                                              # no venue named: never the men's ground
    loc = g("Chelsea", "W:eng.w.1", {"name": "Kingsmeadow", "city": "Kingston upon Thames", "country": "England"})
    assert loc[:2] == (51.405, -0.281)
    assert "Kingsmeadow | Kingston upon Thames" in json.loads((tmp_path / "venues.json").read_text())
