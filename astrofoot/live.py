"""Live track record: pre-registered predictions for real upcoming matches, scored against the market.

  fixtures (with odds) --commit--> ledger/predictions/YYYY-MM-DD.jsonl   (before kickoff, SHA-256 per record)
  results              --settle--> ledger/results.jsonl
  both                 --report--> ledger/track_record.json + ledger/TRACK_RECORD.md

The ledger is plain append-only files meant to be committed to git and pushed before kickoff, so it
survives ephemeral machines and anyone can check that each forecast existed before the match: the
git push time is the timestamp, and the SHA-256 shows the record was not edited afterwards.

Source: football-data.co.uk, the same source (and team naming) as the training data.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import geo, models, service
from .config import ROOT, TIMEZONE_OF_SOURCE_TIMES
from .dataset import LEAGUE_NAMES, devig

LEDGER = Path(os.environ.get("ASTRO_LEDGER", ROOT / "ledger"))
FD = "https://www.football-data.co.uk"
FIXTURE_URLS = [f"{FD}/fixtures.csv", f"{FD}/new_league_fixtures.csv"]
EXTRA_LEAGUES = {"ARG", "AUT", "BRA", "CHN", "DEN", "FIN", "IRL", "JAP", "MEX", "NOR", "POL", "ROM",
                 "RUS", "SUI", "SWE", "USA"}
UA = "astro-football-research/1.0 (track record; contact via repository)"
# Odds preference: Bet365 first, because the model's market baseline was trained on Bet365 odds
ODDS_SETS = [("B365H", "B365D", "B365A"), ("AvgH", "AvgD", "AvgA"), ("PSH", "PSD", "PSA"),
             ("MaxH", "MaxD", "MaxA")]
OU_SETS = [("B365>2.5", "B365<2.5"), ("Avg>2.5", "Avg<2.5"), ("P>2.5", "P<2.5")]
ENGINES = ["market", "engine4", "synthesis", "rao", "chokoisky", "frawley"]


# ----------------------------------------------------------------------------- sources
def fetch_csv(url: str, timeout: float = 30) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return read_csv_bytes(raw)


def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace").replace("\x92", "'")
    df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    # the "new leagues" files use different headings
    return df.rename(columns={"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG",
                              "Res": "FTR", "Country": "Div_country"})


def season_code(kickoff_utc: datetime) -> str:
    y = kickoff_utc.year - (kickoff_utc.month < 7)
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def results_url(div: str, kickoff_utc: datetime) -> str:
    if div in EXTRA_LEAGUES:
        return f"{FD}/new/{div}.csv"
    return f"{FD}/mmz4281/{season_code(kickoff_utc)}/{div}.csv"


# ----------------------------------------------------------------------------- parsing
def _kickoff_utc(date: str, time: str) -> datetime | None:
    try:
        d = pd.to_datetime(str(date), dayfirst=True)
        t = str(time) if isinstance(time, str) and ":" in str(time) else None
        if t is None:
            return None                       # no kickoff time -> no chart angles -> skip
        local = pd.Timestamp(f"{d:%Y-%m-%d} {t}").tz_localize(TIMEZONE_OF_SOURCE_TIMES, ambiguous="NaT",
                                                                nonexistent="NaT")
        return None if pd.isna(local) else local.tz_convert("UTC").to_pydatetime()
    except (ValueError, TypeError):
        return None


def match_key(div: str, local_date: str, home: str, away: str) -> str:
    """Same scheme as dataset.build(): sha1(division + YYYY-MM-DD + home + away)[:12]."""
    return hashlib.sha1(f"{div}{local_date}{home}{away}".encode()).hexdigest()[:12]


def _first_set(row, sets):
    for cols in sets:
        if all(c in row.index for c in cols):
            vals = [pd.to_numeric(row[c], errors="coerce") for c in cols]
            if all(np.isfinite(v) and v > 1.0 for v in vals):
                return [float(v) for v in vals], cols[0][:-1]      # "B365H" -> "B365"
    return None, None


def parse_fixtures(df: pd.DataFrame) -> list[dict]:
    out = []
    div_col = "Div" if "Div" in df.columns else "League"
    for _, r in df.iterrows():
        div = str(r.get(div_col, "")).strip()
        if div not in LEAGUE_NAMES and div not in EXTRA_LEAGUES:
            continue
        ko = _kickoff_utc(r.get("Date"), r.get("Time"))
        home, away = str(r.get("HomeTeam", "")).strip(), str(r.get("AwayTeam", "")).strip()
        odds, book = _first_set(r, ODDS_SETS)
        if ko is None or not home or not away or odds is None:
            continue
        ou, _ = _first_set(r, OU_SETS)
        local_date = pd.Timestamp(ko).tz_convert(TIMEZONE_OF_SOURCE_TIMES).strftime("%Y-%m-%d")
        out.append({"match_key": match_key(div, local_date, home, away), "division": div,
                    "league": LEAGUE_NAMES.get(div, div), "home": home, "away": away,
                    "kickoff_utc": ko.isoformat(), "odds": {"home": odds[0], "draw": odds[1], "away": odds[2]},
                    "odds_source": f"football-data.co.uk {book}",
                    "p_over25": float((1 / ou[0]) / (1 / ou[0] + 1 / ou[1])) if ou else None})
    return out


def parse_results(df: pd.DataFrame) -> dict[str, dict]:
    out = {}
    div_col = "Div" if "Div" in df.columns else "League"
    for _, r in df.iterrows():
        gh, ga = pd.to_numeric(r.get("FTHG"), errors="coerce"), pd.to_numeric(r.get("FTAG"), errors="coerce")
        if not (np.isfinite(gh) and np.isfinite(ga)):
            continue
        div = str(r.get(div_col, "")).strip()
        try:
            local_date = pd.to_datetime(str(r.get("Date")), dayfirst=True).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        home, away = str(r.get("HomeTeam", "")).strip(), str(r.get("AwayTeam", "")).strip()
        out[match_key(div, local_date, home, away)] = {"goals_home": int(gh), "goals_away": int(ga)}
    return out


# ----------------------------------------------------------------------------- ledger io
def _canonical(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), default=_jsonable)


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def seal(rec: dict) -> dict:
    body = {k: v for k, v in rec.items() if k != "sha256"}
    return {**body, "sha256": hashlib.sha256(_canonical(body).encode()).hexdigest()}


def verify(rec: dict) -> bool:
    return seal(rec)["sha256"] == rec.get("sha256")


def read_predictions(ledger: Path = LEDGER) -> list[dict]:
    recs = []
    for p in sorted((ledger / "predictions").glob("*.jsonl")):
        recs += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return recs


def read_results(ledger: Path = LEDGER) -> dict[str, dict]:
    p = ledger / "results.jsonl"
    if not p.exists():
        return {}
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return {r["match_key"]: r for r in rows}


def _append(path: Path, recs: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for r in recs:
            fh.write(_canonical(r) + "\n")


# ----------------------------------------------------------------------------- commit
def predict_fixture(fx: dict, now: datetime) -> dict | None:
    loc = geo.resolve(fx["home"], fx["division"])
    if loc is None:
        return None
    o = fx["odds"]
    inp = {"team_a": fx["home"], "team_b": fx["away"], "kickoff_utc": fx["kickoff_utc"],
           "lat": loc[0], "lon": loc[1], "odds_a": o["home"], "odds_d": o["draw"], "odds_b": o["away"],
           "home_side": "A", "context": "league", "division": fx["division"], "p_over25": fx["p_over25"]}
    a = service.analyse(inp)
    e4, syn = a["engine4"], a["synthesis"]
    preds = {"market": {"fav": a["market"]["p_fav"], "draw": a["market"]["p_draw"], "dog": a["market"]["p_dog"]},
             "synthesis": {k: syn["probabilities"][k] for k in ("fav", "draw", "dog")}}
    if e4:
        preds["engine4"] = {"fav": e4["p_fav"], "draw": e4["p_draw"], "dog": e4["p_dog"]}
    for k, v in a["verdicts"].items():
        preds[k] = {"winner": v["winner"], "goals_fav": v["goals_fav"], "goals_dog": v["goals_dog"],
                    "net": v["net"], "confidence": v["confidence"]}
    return seal({
        **fx, "venue_lat": loc[0], "venue_lon": loc[1], "venue_source": loc[2],
        "favourite": a["fav"], "underdog": a["dog"], "fav_is_home": a["fav_is_a"],
        "committed_at": now.isoformat(timespec="seconds"),
        "model_version": e4["version"] if e4 else None,
        "engine4_gate_open": bool(e4 and e4["gate"]["engine4_in_synthesis"]),
        "guardrails": a["guardrails"], "predictions": preds,
    })


def commit(fixtures: list[dict], now: datetime, horizon_days: float = 4.0, ledger: Path = LEDGER) -> dict:
    done = {r["match_key"] for r in read_predictions(ledger)}
    new, skipped = [], []
    for fx in fixtures:
        ko = datetime.fromisoformat(fx["kickoff_utc"])
        if fx["match_key"] in done or not (now < ko <= now + timedelta(days=horizon_days)):
            continue
        rec = predict_fixture(fx, now)
        if rec is None:
            skipped.append(f"{fx['home']} v {fx['away']} ({fx['division']}): venue unknown")
            continue
        new.append(rec)
        done.add(fx["match_key"])
    if new:
        _append(ledger / "predictions" / f"{now:%Y-%m-%d}.jsonl", new)
    return {"committed": len(new), "skipped": skipped}


# ----------------------------------------------------------------------------- settle
def settle(results: dict[str, dict], now: datetime, ledger: Path = LEDGER, source: str = "football-data.co.uk") -> int:
    settled = read_results(ledger)
    new = []
    for rec in read_predictions(ledger):
        k = rec["match_key"]
        if k in settled or k not in results:
            continue
        r = results[k]
        new.append(seal({"match_key": k, **r, "settled_at": now.isoformat(timespec="seconds"), "source": source}))
    if new:
        _append(ledger / "results.jsonl", new)
    return len(new)


def needed_result_urls(ledger: Path = LEDGER, now: datetime | None = None) -> set[str]:
    now = now or datetime.now(timezone.utc)
    settled = read_results(ledger)
    urls = set()
    for rec in read_predictions(ledger):
        ko = datetime.fromisoformat(rec["kickoff_utc"])
        if rec["match_key"] not in settled and ko + timedelta(hours=2) < now:
            urls.add(results_url(rec["division"], ko))
    return urls


# ----------------------------------------------------------------------------- report
def _outcome(rec, res) -> int:
    """0 favourite won, 1 draw, 2 underdog won (90 minutes)."""
    gf, gd = (res["goals_home"], res["goals_away"]) if rec["fav_is_home"] else (res["goals_away"], res["goals_home"])
    return 0 if gf > gd else 1 if gf == gd else 2


def report(ledger: Path = LEDGER) -> dict:
    preds, results = read_predictions(ledger), read_results(ledger)
    rows, integrity = [], {"records": len(preds), "hash_ok": 0, "late": 0}
    for rec in preds:
        integrity["hash_ok"] += verify(rec)
        if rec["committed_at"] >= rec["kickoff_utc"]:
            integrity["late"] += 1
            continue                          # only pre-kickoff predictions count
        if rec["match_key"] in results:
            rows.append((rec, _outcome(rec, results[rec["match_key"]])))
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "integrity": integrity,
           "pending": sum(1 for r in preds if r["match_key"] not in results), "settled": len(rows), "engines": {}}
    if not rows:
        return out
    y = np.array([o for _, o in rows])
    day = np.array([r["kickoff_utc"][:10] for r, _ in rows])
    PM = np.array([[r["predictions"]["market"][k] for k in ("fav", "draw", "dog")] for r, _ in rows])
    label = {"fav": 0, "draw": 1, "dog": 2}
    for eng in ENGINES:
        have = [i for i, (r, _) in enumerate(rows) if eng in r["predictions"]]
        if not have:
            continue
        idx = np.array(have)
        p0 = rows[have[0]][0]["predictions"][eng]
        e = {"n": len(idx)}
        if "fav" in p0:                                   # probabilistic forecast
            P = np.array([[rows[i][0]["predictions"][eng][k] for k in ("fav", "draw", "dog")] for i in idx])
            P = P / P.sum(1, keepdims=True)
            e.update(models.scores(P, y[idx]))
            if eng != "market" and len(idx) >= 30:
                e["delta_rps_vs_market"] = models.block_bootstrap_delta(
                    models.rps(P, y[idx]), models.rps(PM[idx], y[idx]), day[idx])
        else:                                             # categorical verdict
            pick = np.array([label.get(rows[i][0]["predictions"][eng]["winner"], -1) for i in idx])
            ok = pick >= 0
            hit = pick[ok] == y[idx][ok]
            exp = PM[idx][ok][np.arange(ok.sum()), pick[ok]]
            e.update({"n": int(ok.sum()), "accuracy": float(hit.mean()) if ok.any() else None,
                      "market_expected": float(exp.mean()) if ok.any() else None,
                      "lift_pp": float((hit.mean() - exp.mean()) * 100) if ok.any() else None,
                      "lift_se_pp": float(np.sqrt((exp * (1 - exp)).sum()) / max(ok.sum(), 1) * 100) if ok.any() else None})
        out["engines"][eng] = e
    return out


def write_report(rep: dict, ledger: Path = LEDGER) -> None:
    ledger.mkdir(parents=True, exist_ok=True)
    (ledger / "track_record.json").write_text(json.dumps(rep, indent=1, default=_jsonable))
    L = ["# Live track record", "",
         f"_Updated {rep['generated_at']} · {rep['settled']} settled · {rep['pending']} pending · "
         f"{rep['integrity']['hash_ok']}/{rep['integrity']['records']} records verify · "
         f"{rep['integrity']['late']} excluded as committed after kickoff_", "",
         "Every forecast below was committed to this ledger and pushed to git **before kickoff**. Each record "
         "carries a SHA-256 of its contents. Only these pre-registered forecasts count.", ""]
    if rep["settled"]:
        L += ["## Probabilistic forecasts (lower RPS / log loss is better)", "",
              "| Forecast | n | RPS | Log loss | Accuracy | ΔRPS vs market [95% CI] |", "|---|---|---|---|---|---|"]
        for k in ("market", "engine4", "synthesis"):
            e = rep["engines"].get(k)
            if e:
                d = e.get("delta_rps_vs_market")
                ci = f"{d['delta']:+.5f} [{d['ci95'][0]:+.5f}, {d['ci95'][1]:+.5f}]" if d else "needs n ≥ 30"
                L.append(f"| {k} | {e['n']} | {e['rps']:.4f} | {e['logloss']:.4f} | {100 * e['accuracy']:.1f}% | "
                         f"{'—' if k == 'market' else ci} |")
        L += ["", "## Classical verdicts (hit rate vs what the odds implied for the same picks)", "",
              "| Engine | n | Hit rate | Market expected | Lift (pp) ± 1 SE |", "|---|---|---|---|---|"]
        for k in ("rao", "chokoisky", "frawley"):
            e = rep["engines"].get(k)
            if e and e["n"]:
                L.append(f"| {k} | {e['n']} | {100 * e['accuracy']:.1f}% | {100 * e['market_expected']:.1f}% | "
                         f"{e['lift_pp']:+.1f} ± {e['lift_se_pp']:.1f} |")
    else:
        L.append("No settled matches yet.")
    (ledger / "TRACK_RECORD.md").write_text("\n".join(L) + "\n")


# ----------------------------------------------------------------------------- browsing / top picks
OUTCOMES = ("fav", "draw", "dog")


def records(ledger: Path = LEDGER) -> list[dict]:
    """Every sealed forecast joined with its result (if settled), newest kickoff first."""
    results = read_results(ledger)
    out = []
    for r in read_predictions(ledger):
        res = results.get(r["match_key"])
        outcome = OUTCOMES[_outcome(r, res)] if res else None
        p = r["predictions"]
        probs = p.get("synthesis") or p["market"]
        pick = max(OUTCOMES, key=lambda k: probs[k])
        agree = sum(1 for e in ("rao", "chokoisky", "frawley") if p.get(e, {}).get("winner") == pick)
        out.append({**r, "result": res, "outcome": outcome, "verified": verify(r),
                    "pre_kickoff": r["committed_at"] < r["kickoff_utc"], "status": "settled" if res else "pending",
                    "pick": pick, "pick_p": float(probs[pick]), "classical_agree": agree,
                    "pick_hit": (outcome == pick) if res else None})
    out.sort(key=lambda r: r["kickoff_utc"], reverse=True)
    return out


def top_picks(recs: list[dict], per_day: int = 10) -> dict[str, list[dict]]:
    """Per kickoff date (UTC): the matches whose predicted result is most probable, at most `per_day`.

    The rule uses only the sealed, pre-kickoff probabilities (the synthesis, which equals the market
    while Engine 4's gate is closed), so it can be scored honestly afterwards.
    """
    days: dict[str, list[dict]] = {}
    for r in recs:
        if r["pre_kickoff"]:
            days.setdefault(r["kickoff_utc"][:10], []).append(r)
    return {d: sorted(rs, key=lambda r: (-r["pick_p"], -r["classical_agree"]))[:per_day]
            for d, rs in sorted(days.items(), reverse=True)}


def score_picks(picks: list[dict]) -> dict:
    """Hit rate of settled picks vs the hit rate their probabilities implied."""
    s = [p for p in picks if p["pick_hit"] is not None]
    if not s:
        return {"n": 0}
    hits = sum(p["pick_hit"] for p in s)
    exp = sum(p["pick_p"] for p in s)
    var = sum(p["pick_p"] * (1 - p["pick_p"]) for p in s)
    return {"n": len(s), "hits": hits, "hit_rate": hits / len(s), "expected": exp / len(s),
            "se": var ** 0.5 / len(s)}
