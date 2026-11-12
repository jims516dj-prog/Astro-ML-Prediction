"""Bulk import: xgabora Club-Football-Match-Data (football-data.co.uk derived) -> matches.parquet.

Keeps only matches with a kickoff time, 1X2 odds and a resolvable home location. Source
times are UK clock time (verified: EPL 15:00 kickoffs stay 15:00 through BST).
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from . import geo
from .config import RAW, TIMEZONE_OF_SOURCE_TIMES, WORK

LEAGUE_NAMES = {
    "E0": "England Premier League", "E1": "England Championship", "E2": "England League One",
    "E3": "England League Two", "EC": "England National League", "SC0": "Scotland Premiership",
    "SC1": "Scotland Championship", "SC2": "Scotland League One", "SC3": "Scotland League Two",
    "D1": "Germany Bundesliga", "D2": "Germany 2. Bundesliga", "I1": "Italy Serie A",
    "I2": "Italy Serie B", "SP1": "Spain La Liga", "SP2": "Spain Segunda", "F1": "France Ligue 1",
    "F2": "France Ligue 2", "N1": "Netherlands Eredivisie", "B1": "Belgium Pro League",
    "P1": "Portugal Primeira Liga", "T1": "Turkey Super Lig", "G1": "Greece Super League",
    "ARG": "Argentina", "AUT": "Austria", "BRA": "Brazil", "CHN": "China", "DEN": "Denmark",
    "FIN": "Finland", "IRL": "Ireland", "JAP": "Japan", "MEX": "Mexico", "NOR": "Norway",
    "POL": "Poland", "ROM": "Romania", "RUS": "Russia", "SUI": "Switzerland", "SWE": "Sweden",
    "USA": "USA MLS",
    "MANUAL": "Added manually",
    "UCL": "UEFA Champions League", "UEL": "UEFA Europa League", "UECL": "UEFA Conference League",
}
LEAGUE_NAMES.update({
    "COL": "Colombia Primera A", "ECU": "Ecuador LigaPro", "PAR": "Paraguay Primera", "PER": "Peru Liga 1",
    "URU": "Uruguay Primera", "CHI": "Chile Primera", "AUS": "Australia A-League", "BRA2": "Brazil Serie B",
    "KSA": "Saudi Pro League", "KOR": "South Korea K League 1", "AFCON": "Africa Cup of Nations",
    "N2": "Netherlands Eerste Divisie", "D3": "Germany 3. Liga", "SWE2": "Sweden Superettan",
    "KNVB": "Netherlands KNVB Cup", "TACA": "Portugal Taça de Portugal", "SCUP": "Scotland Scottish Cup",
    "SLC": "Scotland League Cup", "SCC": "Scotland Challenge Cup",
    "FAC": "England FA Cup", "EFLC": "England EFL Cup", "CDR": "Spain Copa del Rey", "DFB": "Germany DFB-Pokal",
    "CIT": "Italy Coppa Italia", "CDF": "France Coupe de France", "LIB": "Copa Libertadores",
    "SUD": "Copa Sudamericana", "CCC": "CONCACAF Champions Cup",
})
# Club competitions across countries: no football-data.co.uk files; fixtures/odds and results come from the
# secondary sources only (fixtures2, fixtures_espn, results2, results_espn).
EUROPEAN = {"UCL", "UEL", "UECL"}
# Cups with clubs from several divisions (or countries): names are matched strictly, grounds looked up.
CUPS = {"FAC", "EFLC", "CDR", "DFB", "CIT", "CDF", "LIB", "SUD", "CCC", "AFCON", "KNVB", "TACA", "SCUP", "SLC", "SCC"}
# Leagues football-data.co.uk does not cover (fixtures, odds and results from ESPN / The Odds API only).
EXTRA_SECONDARY = {"COL", "ECU", "PAR", "PER", "URU", "CHI", "AUS", "BRA2", "KSA", "KOR", "N2", "D3", "SWE2"}
MULTI_CLUB = EUROPEAN | CUPS
DISCOVERED = "X:"          # prefix of competitions found on ESPN by discovery, e.g. "X:bol.1" (fixtures_espn.py)
WOMEN = "W:"               # prefix of women's competitions (own ledger: ledger/women), e.g. "W:eng.w.1"


class _Secondary(frozenset):
    """The competitions without football-data.co.uk files: the fixed ones plus every discovered "X:" code."""

    def __contains__(self, div) -> bool:
        return (isinstance(div, str) and div.startswith((DISCOVERED, WOMEN, "O:"))) or frozenset.__contains__(self, div)


NO_PRIMARY = _Secondary(EUROPEAN | CUPS | EXTRA_SECONDARY)


def league_name(code: str) -> str:
    """Display name of a division: our names, then the names of competitions discovered on ESPN."""
    if code in LEAGUE_NAMES:
        return LEAGUE_NAMES[code]
    if isinstance(code, str) and code.startswith(("O:", "W:o")):
        from .fixtures_oddspapi import league_name as _op
        got = _op(code)
        if got:
            return got
    if isinstance(code, str) and code.startswith(DISCOVERED):
        from .fixtures_espn import discovered_names
        return discovered_names().get(code[len(DISCOVERED):], code[len(DISCOVERED):])
    if isinstance(code, str) and code.startswith(WOMEN):
        from .fixtures_espn import women_names
        return women_names().get(code[len(WOMEN):], code[len(WOMEN):])
    return code


def devig(odds: np.ndarray) -> np.ndarray:
    """Power-method de-vigging: find k with sum(p_i^k) = 1 where p_i = 1/odds_i."""
    p = 1.0 / odds
    lo, hi = np.full(len(p), 0.5), np.full(len(p), 2.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = (p ** k[:, None]).sum(1)
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    q = p ** ((lo + hi) / 2)[:, None]
    return q / q.sum(1, keepdims=True)


def season_of(ts: pd.Series) -> pd.Series:
    y = ts.dt.year - (ts.dt.month < 7).astype(int)
    return y.astype(str) + "/" + ((y + 1) % 100).astype(str).str.zfill(2)


def build() -> pd.DataFrame:
    d = pd.read_csv(RAW / "Matches.csv", low_memory=False)
    d = d[d.MatchTime.notna() & d.OddHome.notna() & d.OddDraw.notna() & d.OddAway.notna()
          & d.FTResult.notna()].copy()
    for c in ("HomeTeam", "AwayTeam"):          # cp1252 apostrophe in a few source rows
        d[c] = d[c].str.replace("\x92", "'", regex=False)
    local = pd.to_datetime(d.MatchDate + " " + d.MatchTime)
    d["kickoff_utc"] = (local.dt.tz_localize(TIMEZONE_OF_SOURCE_TIMES, ambiguous="NaT",
                                             nonexistent="NaT").dt.tz_convert("UTC"))
    d = d[d.kickoff_utc.notna()]
    locs = {}
    for t, dv in d[["HomeTeam", "Division"]].drop_duplicates().itertuples(index=False):
        locs[(t, dv)] = geo.resolve(t, dv)
    ll = [locs[(t, dv)] for t, dv in zip(d.HomeTeam, d.Division)]
    d["lat"] = [x[0] if x else np.nan for x in ll]
    d["lon"] = [x[1] if x else np.nan for x in ll]
    d["loc_source"] = [x[2] if x else None for x in ll]
    d = d[d.lat.notna()].copy()

    odds = d[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
    p = devig(odds)
    d["p_home"], d["p_draw"], d["p_away"] = p[:, 0], p[:, 1], p[:, 2]
    d["overround"] = (1 / odds).sum(1) - 1
    ou = d[["Over25", "Under25"]].to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        d["p_over25"] = (1 / ou[:, 0]) / ((1 / ou).sum(1))
    d["fav_is_home"] = d.OddHome <= d.OddAway
    d["equal_odds"] = (d.OddHome - d.OddAway).abs() <= 0.05
    d["result"] = d.FTResult.map({"H": 0, "D": 1, "A": 2})          # home frame: 0 home win
    d["season"] = season_of(d.kickoff_utc)
    key = d.Division + d.MatchDate + d.HomeTeam + d.AwayTeam
    d["match_id"] = [hashlib.sha1(k.encode()).hexdigest()[:12] for k in key]
    d = d.drop_duplicates("match_id")
    out = pd.DataFrame({
        "match_id": d.match_id, "division": d.Division, "league": d.Division.map(LEAGUE_NAMES),
        "season": d.season, "kickoff_utc": d.kickoff_utc, "local_time_uk": d.MatchTime.str[:5],
        "home": d.HomeTeam, "away": d.AwayTeam, "lat": d.lat, "lon": d.lon,
        "loc_source": d.loc_source, "odds_home": d.OddHome, "odds_draw": d.OddDraw,
        "odds_away": d.OddAway, "p_home": d.p_home, "p_draw": d.p_draw, "p_away": d.p_away,
        "overround": d.overround, "p_over25": d.p_over25, "fav_is_home": d.fav_is_home,
        "equal_odds": d.equal_odds, "elo_home": d.HomeElo, "elo_away": d.AwayElo,
        "form5_home": d.Form5Home, "form5_away": d.Form5Away, "goals_home": d.FTHome.astype(int),
        "goals_away": d.FTAway.astype(int), "result": d.result.astype(int),
        "data_source": "football-data.co.uk via xgabora/Club-Football-Match-Data-2000-2025",
    }).sort_values("kickoff_utc").reset_index(drop=True)
    out = combine_with_live(out)
    out.to_parquet(WORK / "matches.parquet", index=False)
    return out


def live_settled() -> pd.DataFrame:
    """Settled live-ledger matches in the training-table layout (the living engine's daily new data).

    Elo/form are not available for live fixtures; the models no longer use them (see control_matrix).
    """
    from . import live
    rows = []
    for r in live.records():
        if r["status"] != "settled" or not r["pre_kickoff"]:
            continue
        ko = pd.Timestamp(r["kickoff_utc"])
        o = r["odds"]
        p = devig(np.array([[o["home"], o["draw"], o["away"]]]))[0]
        gh, ga = r["result"]["goals_home"], r["result"]["goals_away"]
        rows.append({
            "match_id": r["match_key"], "division": r["division"], "league": LEAGUE_NAMES.get(r["division"], r["division"]),
            "kickoff_utc": ko, "local_time_uk": ko.tz_convert(TIMEZONE_OF_SOURCE_TIMES).strftime("%H:%M"),
            "home": r["home"], "away": r["away"], "lat": r["venue_lat"], "lon": r["venue_lon"],
            "loc_source": r.get("venue_source"), "odds_home": o["home"], "odds_draw": o["draw"], "odds_away": o["away"],
            "p_home": p[0], "p_draw": p[1], "p_away": p[2], "overround": float((1 / np.array(list(o.values()))).sum() - 1),
            "p_over25": r.get("p_over25"), "fav_is_home": o["home"] <= o["away"],
            "equal_odds": abs(o["home"] - o["away"]) <= 0.05, "elo_home": np.nan, "elo_away": np.nan,
            "form5_home": np.nan, "form5_away": np.nan, "goals_home": gh, "goals_away": ga,
            "result": 0 if gh > ga else 1 if gh == ga else 2, "data_source": "live ledger (football-data.co.uk)"})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["kickoff_utc"] = pd.to_datetime(df.kickoff_utc, utc=True)
    df["season"] = season_of(df.kickoff_utc)
    return df


def combine_with_live(hist: pd.DataFrame) -> pd.DataFrame:
    """Historical table + settled live matches; a match present in both keeps the historical row."""
    lv = live_settled()
    if not len(lv):
        return hist
    lv = lv[~lv.match_id.isin(set(hist.match_id))]
    out = pd.concat([hist, lv[hist.columns]], ignore_index=True)
    return out.sort_values("kickoff_utc").reset_index(drop=True)


def frame_view(m: pd.DataFrame, frame: str, seed: int = 7) -> pd.DataFrame:
    """Orient a match table to a team frame. team1 owns the 1st house.

    FAV: favourite = team1 · HOME: home = team1 · COIN: team1 chosen by a fixed coin flip
    per match (negative control - it should carry no more signal than half of the true frame).
    """
    if frame == "FAV":
        t1_home = m.fav_is_home.to_numpy()
    elif frame == "HOME":
        t1_home = np.ones(len(m), bool)
    elif frame == "COIN":
        h = np.array([int(x, 16) for x in m.match_id.str[:8]])
        t1_home = ((h * 2654435761 + seed) % 7919) % 2 == 0
    else:
        raise ValueError(frame)
    r = m.result.to_numpy()
    y = np.where(t1_home, r, 2 - r)
    p1 = np.where(t1_home, m.p_home, m.p_away)
    p2 = np.where(t1_home, m.p_away, m.p_home)
    return pd.DataFrame({
        "y": y, "p1": p1, "pd": m.p_draw.to_numpy(), "p2": p2, "t1_home": t1_home,
        "elo_diff": np.where(t1_home, m.elo_home - m.elo_away, m.elo_away - m.elo_home),
        "form_diff": np.where(t1_home, m.form5_home - m.form5_away, m.form5_away - m.form5_home),
    }, index=m.index)
