"""Tennis live record: forecasts for upcoming singles matches, sealed (SHA-256) before the start and
committed to ledger/tennis by the GitHub cycle, then settled from ESPN's results."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .. import live as football_live
from . import DATA, LEDGER, build, espn, features, model

HORIZON_H = 36          # forecast matches starting within this many hours
VOID_DAYS = 4           # no result this long after the start: void


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def _append(path: Path, recs: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in recs:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")


def predictions(ledger: Path = LEDGER) -> list[dict]:
    return _read(ledger / "predictions.jsonl")


def results(ledger: Path = LEDGER) -> dict[str, dict]:
    return {r["match_id"]: r for r in _read(ledger / "results.jsonl")}


def load_players(ledger: Path = LEDGER) -> pd.DataFrame:
    parts = [pd.read_parquet(DATA / "players.parquet")] if (DATA / "players.parquet").exists() else []
    extra = ledger / "players.json"
    if extra.exists():
        parts.append(pd.DataFrame(json.loads(extra.read_text())))
    if not parts:
        return pd.DataFrame(columns=["id", "name", "full_name", "dob", "birthplace", "hand", "height_in", "country"])
    pl = pd.concat(parts, ignore_index=True)
    pl["id"] = pl["id"].astype(str)
    return pl.drop_duplicates("id", keep="last").reset_index(drop=True)


def load_matches(ledger: Path = LEDGER) -> pd.DataFrame:
    parts = [pd.read_parquet(DATA / "matches.parquet")] if (DATA / "matches.parquet").exists() else []
    recent = ledger / "recent.parquet"
    if recent.exists():
        parts.append(pd.read_parquet(recent))
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True).drop_duplicates("id", keep="last")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["best_of"] = [espn.best_of(t, e, r) for t, e, r in zip(df.tour, df.event, df["round"])]
    return df.sort_values(["date", "id"]).reset_index(drop=True)


def state(matches: pd.DataFrame, now: datetime) -> features.State:
    st = features.State()
    for m in matches[matches.completed & (matches.date < pd.Timestamp(now))].to_dict("records"):
        st.update(m)
    return st


def forecast(st: features.State, m: dict, players: dict, bundle=None) -> dict | None:
    f = features.row(st, m, players)
    p = model.predict(f, bundle)
    if p is None:
        return None
    return {"features": {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in f.items()}, "p": p}


def cycle(now: datetime | None = None, ledger: Path = LEDGER, log=print, crawl=build.crawl, fetch_players=build.players) -> dict:
    now = now or datetime.now(timezone.utc)
    ledger.mkdir(parents=True, exist_ok=True)
    fresh = crawl((now - timedelta(days=45)).date(), (now + timedelta(days=3)).date(), log)
    if not fresh.empty:
        fresh.to_parquet(ledger / "recent.parquet", index=False)
    matches = load_matches(ledger)
    if matches.empty:
        log("tennis: no match data")
        return {"new": 0, "settled": 0}
    # birth details for every player in an upcoming match we do not know yet
    pl = load_players(ledger)
    up = matches[(matches.state == "pre") & (matches.date >= pd.Timestamp(now))
                 & (matches.date <= pd.Timestamp(now + timedelta(hours=HORIZON_H)))]
    need = set(up.p1_id) | set(up.p2_id)
    if need - set(pl.id):
        extra_path = ledger / "players.json"
        extra = pd.DataFrame(json.loads(extra_path.read_text())) if extra_path.exists() else pd.DataFrame()
        got = fetch_players(need - set(pl.id), extra if len(extra) else None, log)
        extra_path.write_text(json.dumps(got.where(got.notna(), None).to_dict("records"), indent=0, default=str))
        pl = load_players(ledger)
    players = features.players_dict(pl)
    bundle = model.load()
    done_ids = {r["match_id"] for r in predictions(ledger)}
    st = state(matches, now)
    new = []
    for m in up.to_dict("records"):
        if m["id"] in done_ids or not m["p1_id"] or not m["p2_id"]:
            continue
        fc = forecast(st, m, players, bundle)
        if fc is None:
            log("tennis: no trained model yet")
            break
        rec = {"match_id": m["id"], "tour": m["tour"], "event": m["event"], "round": m["round"], "venue": m["venue"],
               "surface": m["surface"], "best_of": int(m["best_of"]), "start_utc": m["date"].isoformat(),
               "p1": m["p1"], "p1_id": m["p1_id"], "p1_seed": _seed(m.get("p1_seed")), "p1_country": m.get("p1_country"),
               "p2": m["p2"], "p2_id": m["p2_id"], "p2_seed": _seed(m.get("p2_seed")), "p2_country": m.get("p2_country"),
               "model_version": fc["p"]["version"], "p": fc["p"], "features": fc["features"],
               "committed_at": now.isoformat(timespec="seconds")}
        new.append(football_live.seal(json.loads(json.dumps(rec, default=_plain))))
    _append(ledger / "predictions.jsonl", new)
    # settle
    res, by_id = results(ledger), matches.set_index("id")
    settled = []
    for r in predictions(ledger):
        if r["match_id"] in res:
            continue
        m = by_id.loc[r["match_id"]] if r["match_id"] in by_id.index else None
        if m is not None and isinstance(m, pd.DataFrame):
            m = m.iloc[-1]
        start = datetime.fromisoformat(r["start_utc"])
        if m is not None and bool(m["completed"]):
            void = bool(m["walkover"]) or not m["set_winners"]
            settled.append({"match_id": r["match_id"], "winner": None if void else int(m["winner"]),
                            "set_winners": "" if void else str(m["set_winners"]), "score": str(m["score"]),
                            "retired": bool(m["retired"]), "void": void,
                            "void_reason": "walkover" if bool(m["walkover"]) else ("no sets played" if void else None),
                            "source": "espn.com", "settled_at": now.isoformat(timespec="seconds")})
        elif now - start > timedelta(days=VOID_DAYS):
            settled.append({"match_id": r["match_id"], "winner": None, "set_winners": "", "score": "", "retired": False,
                            "void": True, "void_reason": "no result", "source": "", "settled_at": now.isoformat(timespec="seconds")})
    _append(ledger / "results.jsonl", settled)
    write_report(ledger)
    log(f"tennis: {len(new)} new forecast(s), {len(settled)} settled")
    return {"new": len(new), "settled": len(settled)}


def _seed(v):
    return int(v) if isinstance(v, (int, float, np.integer, np.floating)) and v == v and v else None


def _plain(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    return str(o)


def join(r: dict, res: dict | None) -> dict:
    p = r["p"]
    out = {**r, "result": res, "status": "pending" if res is None else ("void" if res.get("void") else "settled"),
           "verified": football_live.verify(r), "pre_kickoff": r["committed_at"] < r["start_utc"]}
    out["best_of"] = espn.best_of(r.get("tour"), r.get("event"), r.get("round"))   # display: ESPN's was wrong for ATP
    for k in ("p1_seed", "p2_seed"):          # display only: a missing seed may be stored as NaN
        v = r.get(k)
        out[k] = int(v) if isinstance(v, (int, float)) and v == v and v else None
    fav = 1 if p["a_match"] >= 0.5 else 2
    out.update(fav=fav, set_pick=1 if p["a_set"] >= 0.5 else 2, p_set_pick=max(p["a_set"], p["b_set"]),
               first_pick=1 if p["a_first"] >= 0.5 else 2, p_first_pick=max(p["a_first"], p["b_first"]),
               dog=3 - fav, p_dog_one_set=p["b_one_set"] if fav == 1 else p["a_one_set"],
               p_fav_one_set=p["a_one_set"] if fav == 1 else p["b_one_set"])
    if res and not res.get("void"):
        sw = res["set_winners"]
        out.update(sets_a=sw.count("1"), sets_b=sw.count("2"), first_winner=int(sw[0]) if sw else None,
                   dog_won_set=str(out["dog"]) in sw, match_hit=res["winner"] == fav,
                   first_hit=(int(sw[0]) == out["first_pick"]) if sw else None,
                   set_hits=sum(1 for c in sw if int(c) == out["set_pick"]), sets_played=len(sw))
    return out


def records(ledger: Path = LEDGER) -> list[dict]:
    res = results(ledger)
    return sorted((join(r, res.get(r["match_id"])) for r in predictions(ledger)), key=lambda r: r["start_utc"])


def track_record(recs: list[dict]) -> dict:
    """Scores of every settled pre-start forecast: sets (each set played), first set, at least one set
    for the underdog, and the match, each against the rate its own probabilities expected."""
    s = [r for r in recs if r["status"] == "settled" and r["pre_kickoff"]]
    if not s:
        return {"n": 0}
    sets_n = sum(r["sets_played"] for r in s)
    sets_hit = sum(r["set_hits"] for r in s)
    sets_exp = sum(r["p_set_pick"] * r["sets_played"] for r in s)
    out = {"n": len(s), "sets": {"n": sets_n, "hits": sets_hit, "expected": sets_exp / sets_n if sets_n else None}}
    for key, hit, pk in (("first", "first_hit", "p_first_pick"), ("match", "match_hit", None)):
        rows = [r for r in s if r.get(hit) is not None]
        exp = [r[pk] if pk else max(r["p"]["a_match"], r["p"]["b_match"]) for r in rows]
        out[key] = {"n": len(rows), "hits": sum(bool(r[hit]) for r in rows), "expected": float(np.mean(exp)) if rows else None}
    out["dog_one_set"] = {"n": len(s), "hits": sum(bool(r["dog_won_set"]) for r in s),
                          "expected": float(np.mean([r["p_dog_one_set"] for r in s]))}
    for v in out.values():
        if isinstance(v, dict) and v.get("n"):
            v["rate"] = v["hits"] / v["n"]
    return out


def write_report(ledger: Path = LEDGER):
    recs = records(ledger)
    t = track_record(recs)
    lines = ["# Tennis live track record", "", f"Forecasts: {len(recs)} · settled before-start forecasts: {t['n']}", ""]
    for k, label in (("sets", "Sets (favoured player per set)"), ("first", "First set"), ("match", "Match"),
                     ("dog_one_set", "Underdog wins at least one set")):
        v = t.get(k)
        if v and v.get("n"):
            lines.append(f"- {label}: {v['hits']}/{v['n']} ({v['rate']:.1%}), expected {v['expected']:.1%}")
    (ledger / "TRACK_RECORD.md").write_text("\n".join(lines) + "\n")
