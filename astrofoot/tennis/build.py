"""Build the tennis history from ESPN: every singles match (ATP and WTA) month by month, and every
player's date and place of birth. Writes data/tennis/matches.parquet and data/tennis/players.parquet."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

from . import DATA, espn
from .surface import surface

START = date(2010, 1, 1)


def months(d_from: date, d_to: date):
    d = d_from.replace(day=1)
    while d <= d_to:
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield d, min(nxt - timedelta(days=1), d_to)
        d = nxt


def crawl(d_from: date, d_to: date, log=print, get=espn.get_json, workers: int = 6) -> pd.DataFrame:
    """Every singles match ESPN lists between two dates, one row per match (deduplicated by match id)."""
    jobs = [(t, a, b) for a, b in months(d_from, d_to) for t in espn.TOURS]

    def one(job):
        t, a, b = job
        try:
            return job, espn.scoreboard(t, a, b, get), None
        except Exception as e:  # noqa: BLE001
            return job, [], f"{type(e).__name__}: {e}"

    rows, seen = [], set()
    with ThreadPoolExecutor(workers) as ex:
        for (t, a, b), events, err in ex.map(one, jobs):
            if err:
                log(f"  {t} {a:%Y-%m}: unavailable ({err})")
                continue
            for e in events:
                for r in espn.parse_event(e):
                    if r["id"] not in seen and r["date"]:
                        seen.add(r["id"])
                        rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df = df[(df.date.dt.date >= d_from) & (df.date.dt.date <= d_to + timedelta(days=1))]
    df["surface"] = [surface(e, v) for e, v in zip(df.event, df.venue)]
    df["best_of"] = [espn.best_of(t, e, r) for t, e, r in zip(df.tour, df.event, df["round"])]
    return df.sort_values(["date", "id"]).reset_index(drop=True)


def players(ids, known: pd.DataFrame | None = None, log=print, get=espn.get_json, workers: int = 8) -> pd.DataFrame:
    """Birth details of every player id not already known."""
    have = set(known["id"]) if known is not None and len(known) else set()
    todo = sorted({str(i) for i in ids if i} - have)
    log(f"  players: {len(have)} known, fetching {len(todo)}")

    def one(pid):
        try:
            return espn.athlete(pid, get)
        except Exception:  # noqa: BLE001
            return {"id": pid, "name": "", "full_name": "", "dob": None, "birthplace": "", "hand": "",
                    "height_in": None, "country": ""}

    with ThreadPoolExecutor(workers) as ex:
        new = pd.DataFrame(list(ex.map(one, todo)))
    out = pd.concat([known, new], ignore_index=True) if known is not None and len(known) else new
    return out.drop_duplicates("id", keep="last").reset_index(drop=True)


def build(today: date | None = None, log=print, start: date = START) -> dict:
    today = today or date.today()
    DATA.mkdir(parents=True, exist_ok=True)
    mpath, ppath = DATA / "matches.parquet", DATA / "players.parquet"
    old = pd.read_parquet(mpath) if mpath.exists() else pd.DataFrame()
    # refresh the last 60 days every time (late results, corrections); the rest only once
    since = start if old.empty else max(start, (old.date.max() - pd.Timedelta(days=60)).date())
    log(f"crawling ESPN {since} → {today + timedelta(days=7)}")
    new = crawl(since, today + timedelta(days=7), log)
    df = pd.concat([old, new], ignore_index=True) if len(old) else new
    df = df.drop_duplicates("id", keep="last").sort_values(["date", "id"]).reset_index(drop=True)
    df.to_parquet(mpath, index=False)
    known = pd.read_parquet(ppath) if ppath.exists() else None
    pl = players(pd.concat([df.p1_id, df.p2_id]), known, log)
    pl.to_parquet(ppath, index=False)
    done = df[df.completed & ~df.walkover & (df.set_winners.str.len() > 0)]
    by_year = done.groupby([done.date.dt.year, "tour"]).size().unstack(fill_value=0)
    log(by_year.to_string())
    log(f"players with a birth date: {pl.dob.notna().sum()} / {len(pl)}")
    return {"matches": len(df), "completed": len(done), "players": len(pl), "with_dob": int(pl.dob.notna().sum())}
