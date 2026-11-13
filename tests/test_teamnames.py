import json

from astrofoot import teamday, teamnames


def test_fifa_names_for_national_teams():
    cases = {"South Korea": "Korea Republic", "South Korea U21": "Korea Republic U21", "Czech Republic": "Czechia",
             "DR Congo": "Congo DR", "Turkey": "Türkiye", "Iran": "IR Iran", "Ivory Coast": "Côte d'Ivoire",
             "United States": "USA", "Ireland": "Republic of Ireland", "Cape Verde": "Cabo Verde",
             "FYR Macedonia": "North Macedonia", "China": "China PR", "England U-21": "England U21", "Spain W": "Spain W"}
    for given, fifa in cases.items():
        assert teamnames.display(given) == fifa, given
    assert teamnames.legal("South Korea U21") == "Korea Republic"


def test_clubs_short_for_display_legal_for_numerology(tmp_path, monkeypatch):
    f = tmp_path / "names.json"
    f.write_text(json.dumps({"Bayern Munich": {"short": "FC Bayern München", "legal": "Fußball-Club Bayern München e. V."},
                             "W:Barcelona": {"short": "FC Barcelona Femení", "legal": "Futbol Club Barcelona Femení"}}))
    monkeypatch.setattr(teamnames, "FILE", f)
    teamnames.reload()
    try:
        assert teamnames.display("Bayern Munich") == "FC Bayern München"
        assert teamnames.display("Bayern Munich U19") == "FC Bayern München U19"
        assert teamnames.legal("Bayern Munich") == "Fußball-Club Bayern München e. V."
        assert teamnames.display("Unknown FC") == "Unknown FC" and teamnames.legal("Unknown FC") is None
        assert teamnames.legal("Barcelona", women=True) == "Futbol Club Barcelona Femení"
        assert teamnames.legal("Bayern Munich", women=True) is None        # never the men's club's name
        # the day reading's name number uses the legal name
        r = teamday.reading("Bayern Munich", "Unknown FC", "2026-11-14T14:30:00+00:00", 48.2, 11.6, None, False,
                            founded={"home": "1900-02-27", "away": "1901-01-01"})
        assert r["home"]["chart_name"] == "Fußball-Club Bayern München e. V." and r["away"]["chart_name"] == "Unknown FC"
    finally:
        teamnames.reload()


def test_fetch_tidy_and_official_pick():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fo
    assert fo.tidy("Manchester United F.C.") == "Manchester United FC"
    assert fo.tidy("A.F.C. Bournemouth") == "AFC Bournemouth"
    e = {"claims": {"P1448": [
        {"rank": "normal", "mainsnak": {"datavalue": {"value": {"text": "Old Name", "language": "de"}}}, "qualifiers": {"P582": []}},
        {"rank": "normal", "mainsnak": {"datavalue": {"value": {"text": "Fußball-Club Bayern München e. V.", "language": "de"}}}}]},
         "labels": {"en": {"value": "FC Bayern Munich"}, "de": {"value": "FC Bayern München"}}}
    legal, lang = fo.official(e)
    assert legal == "Fußball-Club Bayern München e. V." and fo.short_name(e, lang) == "FC Bayern München"
    e2 = {"labels": {"en": {"value": "FC Barcelona"}, "ca": {"value": "Futbol Club Barcelona"}}}
    assert fo.short_name(e2, "ca") == "FC Barcelona"


def test_official_names_rules():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    e = {"labels": {"en": {"value": "Aris Thessaloniki F.C."}, "el": {"value": "Άρης"}},
         "claims": {"P1448": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {
             "text": "Αθλητικός Σύλλογος Θεσσαλονίκης ο Άρης", "language": "el"}}}}]}}
    assert fon.official(e) == (None, None)                    # numerology needs the Latin script
    assert fon.short_name(e, "el") == "Aris Thessaloniki FC"
    assert fon.names_agree("Aris", e)
    sharjah = {"labels": {"en": {"value": "Sharjah FC"}, "ar": {"value": "نادي الشارقة"}}, "aliases": {}}
    assert not fon.names_agree("Al Nasr", sharjah)
    assert fon.names_agree("KuPS", {"labels": {"en": {"value": "Kuopion Palloseura"}}})
    bilbao = {"labels": {"en": {"value": "Athletic Club"}, "de": {"value": "Athletic Bilbao"}}}
    assert fon.names_agree("Ath Bilbao", bilbao)


def test_names_merge_never_loses_a_name(tmp_path, monkeypatch):
    import json
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    mine = tmp_path / "mine.json"
    main = tmp_path / "main.json"
    mine.write_text(json.dumps({"Zenit": {"tried": "2026-11"}, "Ajax": {"short": "AFC Ajax", "legal": "x", "v": fon.VERSION},
                                "Celta": {"short": "RC Celta de Vigo", "legal": "RC Celta de Vigo", "v": fon.VERSION},
                                "Al Nasr": {"tried": "2026-11", "v": fon.VERSION}}))
    main.write_text(json.dumps({"Zenit": {"short": "FC Zenit", "legal": "FC Zenit", "v": fon.VERSION},
                                "Ajax": {"short": "Ajax", "legal": "Ajax"}, "Celta": {"tried": "2026-11"},
                                "Al Nasr": {"short": "Alshariqa", "legal": "Alshariqa", "v": 2}}))
    monkeypatch.setattr(fon.teamnames, "FILE", mine)
    fon.merge(str(main))
    out = json.loads(mine.read_text())
    assert out["Zenit"]["short"] == "FC Zenit"                # a run whose lookup failed keeps main's name
    assert out["Ajax"]["short"] == "AFC Ajax"                 # the current rules win
    assert out["Celta"]["short"] == "RC Celta de Vigo"
    assert "short" not in out["Al Nasr"]                      # a rejection under the current rules wins


def test_table_candidates_pick_the_right_club():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    from astrofoot import foundings
    if not len(foundings.table()):
        return
    name = {s.split(":", 1)[1]: t for s, t in zip(foundings.table().source, foundings.table().team)}
    pick = lambda team, c: [name.get(q) for q in fon.table_candidates(team, c)[0]]  # noqa: E731
    assert pick("Bielefeld", "DE") == ["Arminia Bielefeld"]
    assert pick("Bristol Rvs", "GB") == ["Bristol Rovers F.C."]
    assert pick("Dynamo Moscow", "RU") == ["FC Dinamo Moscow"]          # not its reserve side
    assert pick("Huracan", "AR") == ["Club Atlético Huracán"]           # not the Posadas namesake
    assert pick("Toronto FC", "US") == ["Toronto FC"]                   # a Canadian club in MLS
    assert pick("Zaglebie", "PL") == []                                 # Lubin or Sosnowiec: not guessed
    assert "Guangzhou F.C." not in pick("Cangzhou", "CN")
    assert "Grêmio FBPA" not in pick("Remo", "BR")
    assert "Watford F.C." not in pick("Waterford", "IE")
    assert pick("OL Lyonnes", None) == []                               # the women's club
    assert fon.table_candidates("Torreense", None)[1] == "PT"           # the country comes from the table


def test_namesakes_resolved_by_where_the_club_plays(monkeypatch):
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    from astrofoot import foundings
    if not len(foundings.table()):
        return
    name = {s.split(":", 1)[1]: t for s, t in zip(foundings.table().source, foundings.table().team)}
    monkeypatch.setattr(fon, "HOME_AT", {"Zaglebie": [(51.40, 16.20)], "Wisla": [(50.07, 19.93)],
                                         "Helsingor": [(56.03, 12.59)], "Tambov": [(52.72, 41.45)]})
    pick = lambda team, c: [name.get(q) for q in fon.table_candidates(team, c)[0]]  # noqa: E731
    assert pick("Zaglebie", "PL") == ["Zagłębie Lubin"]
    assert pick("Wisla", "PL") == ["Wisła Kraków"]
    assert pick("Helsingor", "DK") == ["FC Helsingør"]                 # not Helsingborg, across the strait
    assert pick("Tambov", "RU") == []                                  # not Spartak Tambov, a small namesake
    e = {"claims": {"P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 51.4, "longitude": 16.2}}}}]}}
    assert fon.item_location(e) == (51.4, 16.2)


def test_untrusted_official_names_dropped():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    assert not fon._agrees("Spal", "Ars et Labor Ferrara Calcio")
    assert fon._agrees("Bristol Rvs", "Bristol Rovers FC")
    assert fon.names_agree("Nykoebing FC", {"labels": {"en": {"value": "Nykøbing FC"}}})


def test_initials_must_match():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    lab = lambda n: {"labels": {"en": {"value": n}}}  # noqa: E731
    assert not fon.names_agree("T. Moscow", lab("FC Spartak Moscow"))
    assert fon.names_agree("T. Moscow", lab("FC Torpedo Moscow"))
    assert fon.names_agree("San Martin S.J.", lab("Club Atlético San Martín de San Juan"))


def test_club_abbreviations_are_not_initials_and_search_needs_every_word():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    lab = lambda n: {"labels": {"en": {"value": n}}}  # noqa: E731
    assert fon.names_agree("Manta F.C.", lab("Manta Fútbol Club"))
    assert not fon.names_agree("Volga N. Novgorod", lab("FC Nizhny Novgorod"), strict=True)


def test_club_must_have_existed_while_the_team_played(monkeypatch):
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    monkeypatch.setattr(fon, "PLAYED", {"Volga N. Novgorod": [2012, 2014], "Cesena": [2024, 2026]})
    born = lambda y: {"claims": {"P571": [{"mainsnak": {"datavalue": {"value": {"time": f"+{y}-01-01T00:00:00Z"}}}}]}}  # noqa: E731
    assert not fon.lifetime_ok("Volga N. Novgorod", born(2015))
    assert fon.lifetime_ok("Volga N. Novgorod", born(1963))


def test_refounded_club_and_namesake_tie_break(monkeypatch):
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    monkeypatch.setattr(fon, "PLAYED", {"Cesena": [2024, 2026], "Atl. San Luis": [2012, 2026]})
    gone = {"claims": {"P576": [{"mainsnak": {"datavalue": {"value": {"time": "+2018-01-01T00:00:00Z"}}}}]}}
    assert not fon.lifetime_ok("Cesena", gone)                # the old club, dissolved before the team played
    born = {"claims": {"P571": [{"mainsnak": {"datavalue": {"value": {"time": "+2017-01-01T00:00:00Z"}}}}]}}
    assert fon.lifetime_ok("Atl. San Luis", born)             # one name across a club and its refounding
    city = {"labels": {"en": {"value": "Guangzhou City F.C."}}, "aliases": {"en": [{"value": "Guangzhou R&F"}]}}
    fc = {"labels": {"en": {"value": "Guangzhou F.C."}}, "aliases": {"en": [{"value": "Guangzhou Evergrande"}]}}
    mine = fon._tokens("Guangzhou R&F")
    assert mine <= fon.item_tokens(city) and not mine <= fon.item_tokens(fc)


def test_spelling_variants_only_by_a_vowel():
    import sys
    sys.path.insert(0, "scripts")
    import fetch_official_names as fon
    assert fon._abbrev_ok("dynamo", {"dinamo"}) and fon._abbrev_ok("nykoebing", {"nykobing"})
    assert not fon._abbrev_ok("ceuta", {"celta"}) and not fon._abbrev_ok("remo", {"gremio"})
