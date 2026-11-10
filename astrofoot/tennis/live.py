"""Tennis live record: forecasts for upcoming singles matches, sealed (SHA-256) before the start and
committed to ledger/tennis by the GitHub cycle, then settled from ESPN's results."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .. import live as football_live
from . import DATA, LEDGER, build, daychart, espn, features, model
from . import odds as tennis_odds

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


def day_compare(m: dict, players: dict) -> dict:
    """Date-only astrology and numerology of both players for the match day, and who each favours."""
    from .venue import local_day
    day, tz = local_day(m.get("venue") or "", m.get("date") or m.get("start_utc"))
    pa, pb = players.get(str(m["p1_id"]), {}), players.get(str(m["p2_id"]), {})
    aa, ab = daychart.astro_day(pa.get("dob"), day, tz), daychart.astro_day(pb.get("dob"), day, tz)
    na = daychart.num_day(pa.get("dob"), pa.get("full_name") or m["p1"], day)
    nb = daychart.num_day(pb.get("dob"), pb.get("full_name") or m["p2"], day)
    return {"day": day, "tz": tz, "venue": m.get("venue") or "", "dob": {"a": daychart.an.clean_dob(pa.get("dob")), "b": daychart.an.clean_dob(pb.get("dob"))},
            "astro": {"a": aa, "b": ab, "favours": daychart.verdict(aa["score"], ab["score"])},
            "num": {"a": na, "b": nb, "favours": daychart.verdict(na["score"], nb["score"], 0.4)}}


def forecast(st: features.State, m: dict, players: dict, bundle=None, odds: dict | None = None) -> dict | None:
    f = features.row(st, m, players)
    p = model.predict(f, bundle, odds=(odds["a"], odds["b"]) if odds else None)
    if p is None:
        return None
    keep = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in f.items()
            if not k.startswith("d_astro_") and not k.startswith("d_num_") or k in ("d_astro_rule", "d_num_rule")}
    return {"features": keep, "p": p, "day": day_compare(m, players), "odds": odds}


def cycle(now: datetime | None = None, ledger: Path = LEDGER, log=print, crawl=build.crawl, fetch_players=build.players,
          odds_fetch=tennis_odds.fetch) -> dict:
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
    up = up[pd.Series([not (features.placeholder(a, x) or features.placeholder(b, y))
                       for a, x, b, y in zip(up.p1_id, up.p1, up.p2_id, up.p2)], index=up.index, dtype=bool)]
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
    todo = [m for m in up.to_dict("records") if m["id"] not in done_ids]
    priced = odds_fetch(todo, now, ledger, log=log) if todo else {}
    st = state(matches, now)
    new = []
    for m in up.to_dict("records"):
        if m["id"] in done_ids or not m["p1_id"] or not m["p2_id"]:
            continue
        fc = forecast(st, m, players, bundle, priced.get(m["id"]))
        if fc is None:
            log("tennis: no trained model yet")
            break
        rec = {"match_id": m["id"], "tour": m["tour"], "event": m["event"], "round": m["round"], "venue": m["venue"],
               "surface": m["surface"], "best_of": int(m["best_of"]), "start_utc": m["date"].isoformat(),
               "p1": m["p1"], "p1_id": m["p1_id"], "p1_seed": _seed(m.get("p1_seed")), "p1_country": m.get("p1_country"),
               "p2": m["p2"], "p2_id": m["p2_id"], "p2_seed": _seed(m.get("p2_seed")), "p2_country": m.get("p2_country"),
               "model_version": fc["p"]["version"], "p": fc["p"], "features": fc["features"], "day": fc["day"],
               "odds": fc["odds"],
               "committed_at": now.isoformat(timespec="seconds")}
        new.append(football_live.seal(json.loads(json.dumps(rec, default=_plain))))
    _append(ledger / "predictions.jsonl", new)
    # settle
    res, by_id = results(ledger), matches.set_index("id")
    settled = []
    for r in predictions(ledger):
        if r["match_id"] in res:
            continue
        if _tbd(r):     # sealed before the fix that skips not-yet-known players
            settled.append({"match_id": r["match_id"], "winner": None, "set_winners": "", "score": "", "retired": False,
                            "void": True, "void_reason": TBD_REASON, "source": "", "settled_at": now.isoformat(timespec="seconds")})
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


TBD_REASON = "a player was still TBD (not yet known) when forecast"


def _tbd(r: dict) -> bool:
    return features.placeholder(r.get("p1_id"), r.get("p1")) or features.placeholder(r.get("p2_id"), r.get("p2"))


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
    if res is None and _tbd(r):      # void at once, before the next cycle writes it to the ledger
        res = {"match_id": r["match_id"], "winner": None, "set_winners": "", "score": "", "retired": False, "void": True,
               "void_reason": TBD_REASON}
    out = {**r, "result": res, "status": "pending" if res is None else ("void" if res.get("void") else "settled"),
           "verified": football_live.verify(r), "pre_kickoff": r["committed_at"] < r["start_utc"]}
    out["best_of"] = espn.best_of(r.get("tour"), r.get("event"), r.get("round"))   # display: ESPN's was wrong for ATP
    for k in ("p1_seed", "p2_seed"):          # display only: a missing seed may be stored as NaN
        v = r.get(k)
        out[k] = int(v) if isinstance(v, (int, float)) and v == v and v else None
    # the headline figures: 'expected' (statistics + learned astrology/numerology, blended with the odds when
    # there are any); forecasts sealed before those existed use the statistics model
    e = p.get("expected") or {k: p[k] for k in p if k[:2] in ("a_", "b_")}
    out["e"] = e
    fav = 1 if e["a_match"] >= 0.5 else 2
    out.update(fav=fav, set_pick=1 if e["a_set"] >= 0.5 else 2, p_set_pick=max(e["a_set"], e["b_set"]),
               first_pick=1 if e["a_first"] >= 0.5 else 2, p_first_pick=max(e["a_first"], e["b_first"]),
               match_pick=fav, p_match_pick=max(e["a_match"], e["b_match"]),
               one_pick=1 if e["a_one_set"] >= e["b_one_set"] else 2, p_one_pick=max(e["a_one_set"], e["b_one_set"]),
               dog=3 - fav, p_dog_one_set=e["b_one_set"] if fav == 1 else e["a_one_set"],
               p_fav_one_set=e["a_one_set"] if fav == 1 else e["b_one_set"])
    if res and not res.get("void"):
        sw = res["set_winners"]
        out.update(sets_a=sw.count("1"), sets_b=sw.count("2"), first_winner=int(sw[0]) if sw else None,
                   dog_won_set=str(out["dog"]) in sw, match_hit=res["winner"] == fav,
                   first_hit=(int(sw[0]) == out["first_pick"]) if sw else None,
                   one_hit=str(out["one_pick"]) in sw,
                   set_hits=sum(1 for c in sw if int(c) == out["set_pick"]), sets_played=len(sw))
    return out


def with_odds(r: dict, odds: dict, bundle=None) -> dict:
    """A forecast sealed without odds, seen with odds entered by hand: the odds' set / match chances and the
    expected figure recomputed exactly as the cycle does when it has odds. The sealed record is not changed."""
    bundle = bundle or model.load() or {}
    p = r["p"]
    base = p.get("combined") or {k: v for k, v in p.items() if k[:2] in ("a_", "b_")}
    bo = espn.best_of(r.get("tour"), r.get("event"), r.get("round"))
    mk = model.market_probs(odds["a"], odds["b"], bo, bundle.get("maps") or {})
    if mk is None:
        return r
    exp, wm = dict(base), 0.0
    if "a_set" in mk:
        wm = float(bundle.get("market_weight", model.MARKET_WEIGHT))
        for h in model.HEADS:
            for s_ in ("a", "b"):
                exp[f"{s_}_{h}"] = float(model._sig((1 - wm) * model._logit(base[f"{s_}_{h}"]) + wm * model._logit(mk[f"{s_}_{h}"])))
        for h in ("set", "first", "match"):
            exp[f"b_{h}"] = 1 - exp[f"a_{h}"]
    else:            # no mapping in this model: blend the match chance only
        wm = float(bundle.get("market_weight", model.MARKET_WEIGHT))
        exp["a_match"] = float(model._sig((1 - wm) * model._logit(base["a_match"]) + wm * model._logit(mk["a_match"])))
        exp["b_match"] = 1 - exp["a_match"]
    entered = odds.get("entered_at") or ""
    return {**r, "p": {**p, "combined": base, "market": mk, "expected": exp, "market_weight": wm},
            "odds": {"a": float(odds["a"]), "b": float(odds["b"]), "manual": True, "entered_at": entered,
                     "after_start": bool(entered) and entered >= r["start_utc"],
                     "source": "entered by you" + (" after the start" if entered and entered >= r["start_utc"] else "")}}


def records(ledger: Path = LEDGER, user_odds: dict | None = None) -> list[dict]:
    """Every forecast joined with its result. user_odds ({match_id: {"a", "b", "entered_at"}}) fills in odds for
    forecasts sealed without any; the seal is still checked against the sealed record."""
    res = results(ledger)
    out = []
    bundle = model.load() if user_odds else None
    for r in predictions(ledger):
        o = (user_odds or {}).get(r["match_id"])
        if o and not r.get("odds"):
            j = join(with_odds(r, o, bundle), res.get(r["match_id"]))
            j["verified"] = football_live.verify(r)
        else:
            j = join(r, res.get(r["match_id"]))
        out.append(j)
    return sorted(out, key=lambda r: r["start_utc"])


def track_record(recs: list[dict]) -> dict:
    """Scores of every settled pre-start forecast: sets (each set played), first set, at least one set
    for the underdog, and the match, each against the rate its own probabilities expected."""
    s = [r for r in recs if r["status"] == "settled" and r["pre_kickoff"] and not r.get("manual")]
    if not s:
        return {"n": 0}
    sets_n = sum(r["sets_played"] for r in s)
    sets_hit = sum(r["set_hits"] for r in s)
    sets_exp = sum(r["p_set_pick"] * r["sets_played"] for r in s)
    out = {"n": len(s), "sets": {"n": sets_n, "hits": sets_hit, "expected": sets_exp / sets_n if sets_n else None}}
    for key, hit, pk in (("first", "first_hit", "p_first_pick"), ("match", "match_hit", None)):
        rows = [r for r in s if r.get(hit) is not None]
        exp = [r[pk] if pk else r["p_match_pick"] for r in rows]
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
