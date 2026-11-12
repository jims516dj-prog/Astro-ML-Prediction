"""Tennis live record: forecasts for upcoming singles matches, sealed (SHA-256) before the start and
committed to ledger/tennis by the GitHub cycle, then settled from ESPN's results."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .. import live as football_live
from . import DATA, LEDGER, build, daychart, espn, features, model, venue
from . import lta
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


def _norm_name(n: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in s.replace("-", " ").split())


def _lta_to_espn_ids(df: pd.DataFrame, matches: pd.DataFrame, ledger: Path) -> pd.DataFrame:
    """Players ESPN knows (same name, one id) keep their ESPN id, so their ratings and form apply; the others keep
    their Live Tennis API id. Birthdays from the API go to ledger/tennis/players.json for the astrology."""
    names: dict[str, set] = {}
    if len(matches):
        for i, n in zip(pd.concat([matches.p1_id, matches.p2_id]), pd.concat([matches.p1, matches.p2])):
            if not str(i).startswith("-"):
                names.setdefault(_norm_name(n), set()).add(str(i))
    df = df.copy()
    dobs = {}
    for side in ("p1", "p2"):
        new_ids = []
        for i, n, dob, hand in zip(df[f"{side}_id"], df[side], df["_dob"], df["_hand"]):
            ids = names.get(_norm_name(n), set())
            new = next(iter(ids)) if len(ids) == 1 else i
            new_ids.append(new)
            if dob.get(i):
                dobs[new] = {"id": new, "name": n, "full_name": n, "dob": str(dob[i])[:10], "birthplace": "",
                             "hand": (hand.get(i) or "")[:1].upper(), "height_in": None, "country": ""}
        df[f"{side}_id"] = new_ids
    if dobs:
        path = ledger / "players.json"
        have = json.loads(path.read_text()) if path.exists() else []
        known = {str(p["id"]) for p in have}
        espn_dob = {str(p["id"]) for p in have if p.get("dob")}
        add = [v for k, v in dobs.items() if k not in known or (k not in espn_dob and v["dob"])]
        if add:
            keep = [p for p in have if str(p["id"]) not in {a["id"] for a in add}]
            path.write_text(json.dumps(keep + add, indent=0, default=str))
    return df


def _espn_has(r: dict, up: pd.DataFrame) -> bool:
    """The same match already listed by ESPN (same two players within 36 hours)."""
    if up.empty:
        return False
    a, b, t = _norm_name(r["p1"]), _norm_name(r["p2"]), pd.Timestamp(r["date"])
    for x in up.to_dict("records"):
        if {_norm_name(x["p1"]), _norm_name(x["p2"])} == {a, b} and abs((pd.Timestamp(x["date"]) - t).total_seconds()) < 36 * 3600:
            return True
    return False


def effective_start(venue_name: str, when) -> pd.Timestamp:
    """ESPN's start, or midnight at the venue on the date for its date-only placeholder."""
    w = pd.Timestamp(when)
    if venue.date_only(w):
        return pd.Timestamp(venue.day_start_utc(venue_name, venue.local_day(venue_name, w)[0]))
    return w


def _lta_history(ledger: Path) -> pd.DataFrame:
    """Settled Challenger / team-event forecasts as completed matches, so those players build up ratings and form."""
    res = results(ledger)
    rows = []
    for r in predictions(ledger):
        x = res.get(r["match_id"])
        if not r["match_id"].startswith(lta.PREFIX) or not x or x.get("void") or not x.get("set_winners"):
            continue
        rows.append({"id": r["match_id"], "event_id": "", "event": r["event"], "tour": r["tour"], "level": r.get("level"),
                     "date": pd.Timestamp(r["start_utc"]), "venue": r.get("venue") or "", "round": r.get("round") or "",
                     "best_of": int(r.get("best_of") or 3), "state": "post", "status": "completed", "completed": True,
                     "p1_id": str(r["p1_id"]), "p1": r["p1"], "p1_country": r.get("p1_country") or "", "p1_seed": None,
                     "p1_entry": None, "p1_rank": None, "p2_id": str(r["p2_id"]), "p2": r["p2"],
                     "p2_country": r.get("p2_country") or "", "p2_seed": None, "p2_entry": None, "p2_rank": None,
                     "winner": int(x["winner"]), "score": x.get("score") or "", "set_winners": x["set_winners"],
                     "retired": bool(x.get("retired")), "walkover": False, "note": "", "surface": r.get("surface") or "hard"})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"], utc=True)
    return out


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
    lta_rows = _lta_history(ledger)
    if len(lta_rows):
        df = pd.concat([df, lta_rows], ignore_index=True).drop_duplicates("id", keep="last")
    from . import ids
    df = ids.apply(df, ids.aliases(df, load_players(ledger)))      # one id per player
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
          odds_fetch=tennis_odds.fetch, lta_client=None) -> dict:
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
    # the start used for forecasting: ESPN's time, or for its date-only placeholder (time not set yet) midnight at the
    # venue that day, so a date-only match is forecast before its day begins and never after it may have started
    matches = matches.assign(start=[effective_start(v, d) for v, d in zip(matches.venue.fillna(""), matches.date)])
    up = matches[(matches.state == "pre") & (matches.start >= pd.Timestamp(now))
                 & (matches.start <= pd.Timestamp(now + timedelta(hours=HORIZON_H)))]
    up = up[pd.Series([not (features.placeholder(a, x) or features.placeholder(b, y))
                       for a, x, b, y in zip(up.p1_id, up.p1, up.p2_id, up.p2)], index=up.index, dtype=bool)]
    # Challenger and team-event matches (Live Tennis API, free tier), when its key is set
    client = lta_client
    if client is None and lta.token():
        client = lta.Client(lta.token(), ledger / "lta_state.json", now)
    if client is not None:
        extra_up = lta.upcoming(client, log)
        if len(extra_up):
            extra_up = _lta_to_espn_ids(extra_up, matches, ledger)
            extra_up = extra_up.assign(start=extra_up.date)
            extra_up = extra_up[(extra_up.start >= pd.Timestamp(now))
                                & (extra_up.start <= pd.Timestamp(now + timedelta(hours=HORIZON_H)))]
            extra_up = extra_up[[not _espn_has(r, up) for r in extra_up.to_dict("records")]]
            log(f"tennis: {len(extra_up)} Challenger / team-event match(es) from {lta.SOURCE} within {HORIZON_H} h")
            up = pd.concat([up, extra_up.drop(columns=[c for c in extra_up.columns if c.startswith("_")])],
                           ignore_index=True)
            pl = load_players(ledger)          # with the birthdays the API just gave
    need = {i for i in set(up.p1_id) | set(up.p2_id) if not str(i).startswith(lta.PREFIX)}
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
        rec = {"match_id": m["id"], "tour": m["tour"], "level": m.get("level") or "tour",
               "source": lta.SOURCE if str(m["id"]).startswith(lta.PREFIX) else "espn.com", "event": m["event"], "round": m["round"], "venue": m["venue"],
               "surface": m["surface"], "best_of": int(m["best_of"]), "start_utc": m["start"].isoformat(),
               "time_known": not venue.date_only(m["date"]), "scheduled_utc": m["date"].isoformat(),
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
    if client is not None:
        pend = [r for r in predictions(ledger) if r["match_id"] not in res and r["match_id"].startswith(lta.PREFIX)]
        for mid, x in lta.settle(pend, client, now, log).items():
            settled.append({"match_id": mid, **{k: v for k, v in x.items() if k != "walkover"}, "source": lta.SOURCE,
                            "settled_at": now.isoformat(timespec="seconds")})
        client.save()
        res = {**res, **{x["match_id"]: x for x in settled}}
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
                            "source": "espn.com", "settled_at": now.isoformat(timespec="seconds"),
                            # ESPN's final scheduled start (the order of play moves); None if it never set a time
                            "start_final": None if venue.date_only(m["date"]) else pd.Timestamp(m["date"]).isoformat()})
        elif now - start > timedelta(days=VOID_DAYS + (3 if r["match_id"].startswith(lta.PREFIX) else 0)):
            settled.append({"match_id": r["match_id"], "winner": None, "set_winners": "", "score": "", "retired": False,
                            "void": True, "void_reason": "no result", "source": "", "settled_at": now.isoformat(timespec="seconds")})
    _append(ledger / "results.jsonl", settled)
    write_report(ledger)
    log(f"tennis: {len(new)} new forecast(s), {len(settled)} settled")
    return {"new": len(new), "settled": len(settled)}


def _start_for_scoring(r: dict, res: dict | None) -> str:
    """A forecast counts only if sealed before the match could have started: the sealed start, or ESPN's final
    scheduled start if the match was moved earlier. A sealed date-only placeholder (midnight US Eastern) counts as
    midnight at the venue that day."""
    start = r["start_utc"]
    if r.get("time_known") is None and venue.date_only(start):
        start = venue.day_start_utc(r.get("venue") or "", venue.local_day(r.get("venue") or "", start)[0]).isoformat()
    final = (res or {}).get("start_final")
    return min(start, pd.Timestamp(final).isoformat()) if final else start


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


def predictions_keys(r: dict) -> set[str]:
    """The keys of a sealed record (a joined record adds others)."""
    joined = {"result", "status", "verified", "pre_kickoff", "e", "fav", "set_pick", "p_set_pick", "first_pick",
              "p_first_pick", "match_pick", "p_match_pick", "one_pick", "p_one_pick", "dog", "p_dog_one_set", "p_fav_one_set",
              "sets_a", "sets_b", "first_winner", "dog_won_set", "match_hit", "first_hit", "one_hit", "set_hits",
              "sets_played", "dayv", "pick", "when", "manual", "result_by_you"}
    return set(r) - joined


def join(r: dict, res: dict | None) -> dict:
    p = r["p"]
    if res is None and _tbd(r):      # void at once, before the next cycle writes it to the ledger
        res = {"match_id": r["match_id"], "winner": None, "set_winners": "", "score": "", "retired": False, "void": True,
               "void_reason": TBD_REASON}
    out = {**r, "result": res, "status": "pending" if res is None else ("void" if res.get("void") else "settled"),
           "verified": football_live.verify(r), "pre_kickoff": r["committed_at"] < _start_for_scoring(r, res)}
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
