import csv

import pytest

from astrofoot import db, foundings
from astrofoot.config import RAW

ROWS = [
    {"team": "Manchester United F.C.", "kind": "club", "founded_date": "1878-03-05", "date_precision": "day",
     "founded_time": "", "place": "Newton Heath", "lat": "53.4900", "lon": "-2.1800", "country": "United Kingdom",
     "aliases": "Man United|Manchester United|Newton Heath LYR F.C.", "source": "wikidata:Q18656"},
    {"team": "Brazil national football team", "kind": "national_team", "founded_date": "1914-07-21",
     "date_precision": "day", "founded_time": "", "place": "Rio de Janeiro", "lat": "-22.9", "lon": "-43.2",
     "country": "Brazil", "aliases": "Brazil|Seleção", "source": "wikidata:Q83459"},
    {"team": "Brazil national football team", "kind": "nation", "founded_date": "1822-09-07",
     "date_precision": "day", "founded_time": "", "place": "Brasília", "lat": "-15.79", "lon": "-47.88",
     "country": "Brazil", "aliases": "Brazil|Seleção", "source": "wikidata:Q155"},
    {"team": "Year Only FC", "kind": "club", "founded_date": "1900-01-01", "date_precision": "year",
     "founded_time": "", "place": "", "lat": "51.5", "lon": "0.0", "country": "", "aliases": "", "source": "wikidata:Q1"},
]


@pytest.fixture
def table(tmp_path, monkeypatch):
    p = tmp_path / "team_foundings.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ROWS[0]))
        w.writeheader()
        w.writerows(ROWS)
    monkeypatch.setattr(foundings, "TABLE", p)
    foundings.table.cache_clear()
    yield
    foundings.table.cache_clear()


def test_alias_and_short_names_autofill(table):
    assert foundings.best("Man United")["source"] == "wikidata:Q18656"          # football-data short name
    assert foundings.best("manchester united fc")["founded_date"] == "1878-03-05"
    assert foundings.best("Manchester Utd") is None                             # close only -> suggest, don't auto-fill
    assert any(c["match"] == "close" for c in foundings.search("Manchester Utd"))


def test_ambiguous_names_are_ranked_by_prominence(tmp_path, monkeypatch):
    rows = [dict(ROWS[0], team="Arsenal", aliases="", sitelinks="3", source="wikidata:Q2"),
            dict(ROWS[0], team="Arsenal F.C.", aliases="Arsenal|The Gunners", sitelinks="95", source="wikidata:Q9617"),
            dict(ROWS[0], team="Celtic", aliases="", sitelinks="40", source="wikidata:Q3"),
            dict(ROWS[0], team="Celtic F.C.", aliases="Celtic", sitelinks="60", source="wikidata:Q19593")]
    p = tmp_path / "t.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    monkeypatch.setattr(foundings, "TABLE", p)
    foundings.table.cache_clear()
    assert foundings.best("Arsenal")["source"] == "wikidata:Q9617"     # 95 vs 3: clear, auto-fill
    assert foundings.best("Celtic") is None                           # 60 vs 40: ambiguous, ask
    assert foundings.search("Celtic")[0]["source"] == "wikidata:Q19593"
    foundings.table.cache_clear()


def test_nation_offered_alongside_national_team(table):
    kinds = [c["kind"] for c in foundings.search("Brazil")]
    assert kinds[:2] == ["nation", "national_team"]                              # Rao's nation chart first


def test_saved_chart_takes_priority(table, tmp_path):
    con = db.connect(tmp_path / "t.sqlite3")
    db.save_team_chart(con, "Man United", "1902-04-24", "19:00", "Manchester", 53.48, -2.24, based_on="manual")
    b = foundings.best("Man United", con)
    assert b["kind"] == "manual" and b["founded_time"] == "19:00"


def test_year_only_dates_are_not_usable(table):
    ok, why = foundings.usable(foundings.best("Year Only FC"))
    assert not ok and "year" in why


@pytest.mark.skipif(not (RAW / "csv-cities.csv.gz").exists(), reason="run python scripts/fetch_data.py --live")
def test_cast_without_time_is_noon_local_and_flags_moon(table):
    rc, meta = foundings.cast(foundings.best("Man United"))
    assert rc["time_known"] is False and meta["local"].startswith("1878-03-05 12:00")
    assert meta["moon_sign_certain"] in (True, False)
    rc2, meta2 = foundings.cast({**foundings.best("Man United"), "founded_time": "19:30"})
    assert rc2["time_known"] is True and rc2["asc"] != rc["asc"]
