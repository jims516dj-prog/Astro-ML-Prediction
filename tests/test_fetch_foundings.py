import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("ff", Path(__file__).resolve().parent.parent / "scripts" / "fetch_foundings.py")
ff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ff)
W = "http://www.wikidata.org/entity/"


def item(lab, als=(), **claims):
    def snak(v):
        val = {"id": v} if isinstance(v, str) else {"latitude": v[0], "longitude": v[1]}
        return {"mainsnak": {"datavalue": {"value": val}}}
    return {"labels": {"en": {"value": lab}}, "aliases": {"en": [{"value": a} for a in als]},
            "claims": {p: [snak(v) for v in vs] for p, vs in claims.items()}}


ENTS = {
    "Q18656": item("Manchester United F.C.", ["Man United"], P17=["Q145"], P740=["Q1"], P115=["Q2"]),
    "Q1": item("Newton Heath"),                                   # no coordinates -> fall through
    "Q2": item("Old Trafford", P625=[(53.4631, -2.2913)]),
    "Q145": item("United Kingdom"),
    "Q83459": item("Brazil national football team", ["Brazil", "Seleção"], P159=["Q8678"]),
    "Q8678": item("Rio de Janeiro", P625=[(-22.91, -43.2)]),
    "Q155": item("Brazil", P36=["Q2844"]),
    "Q2844": item("Brasília", P625=[(-15.79, -47.88)]),
}


def fake(ids, props="labels|aliases|claims"):
    return {i: ENTS[i] for i in ids if i in ENTS}


def test_build_rows_places_aliases_and_nation():
    clubs = [{"item": W + "Q18656", "inc": "1878-03-05T00:00:00Z", "pr": "11"}]
    national = [{"item": W + "Q83459", "inc": "1914-07-21T00:00:00Z", "pr": "11",
                 "nation": W + "Q155", "ninc": "1822-09-07T00:00:00Z", "npr": "11"}]
    rows = {(r["team"], r["kind"]): r for r in ff.build_rows(clubs, national, fetch=fake)}
    mu = rows[("Manchester United F.C.", "club")]
    assert (mu["founded_date"], mu["date_precision"], mu["place"], mu["lat"]) == ("1878-03-05", "day", "Old Trafford", "53.46310")
    assert mu["aliases"] == "Man United" and mu["country"] == "United Kingdom" and mu["founded_time"] == ""
    nt = rows[("Brazil national football team", "national_team")]
    assert nt["place"] == "Rio de Janeiro" and nt["country"] == "Brazil"
    na = rows[("Brazil national football team", "nation")]
    assert (na["founded_date"], na["place"], na["source"]) == ("1822-09-07", "Brasília", "wikidata:Q155")


def test_precision_mapping():
    assert ff.date_of("+1900-00-00T00:00:00Z", "9") == ("1900-00-00", "year")
    assert ff.date_of("1878-03-05T00:00:00Z", "11") == ("1878-03-05", "day")
