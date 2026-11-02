"""Team founding charts: lookup (Wikidata table + the user's own saved edits) and chart casting.

Sources, in priority order:
  1. the user's saved charts (SQLite `team_charts`, written from the Analyze form)
  2. data/ref/team_foundings.csv, built from Wikidata by scripts/fetch_foundings.py

Founding dates almost never come with a time. Without one the chart is cast for local noon:
the Moon is then known to about +/-6.5 degrees (its sign is checked across the whole day) and
the Ascendant/houses are unknown, so Rao's step uses the Moon only.
"""
from __future__ import annotations

import difflib
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

from . import ephem, geo
from .config import REF

TABLE = REF / "team_foundings.csv"
KIND_LABEL = {"club": "club founding", "national_team": "national team founding",
              "nation": "nation (state) founding", "manual": "your saved chart"}
_STRIP = {"fc", "cf", "afc", "sc", "ac", "the", "club", "football", "futbol", "fk", "sk", "bk", "if", "cd"}


def _key(s: str) -> str:
    # "Liverpool F.C." -> "liverpool"; dots removed first so F.C./A.F.C. become fc/afc and are dropped
    return " ".join(t for t in geo.norm(str(s).replace(".", "")).split() if t not in _STRIP)


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    if not TABLE.exists():
        return pd.DataFrame()
    t = pd.read_csv(TABLE, dtype=str, keep_default_na=False)
    t["names"] = [[n for n in [team, *aliases.split("|")] if n] for team, aliases in zip(t.team, t.aliases)]
    t["keys"] = [{_key(n) for n in names} - {""} for names in t.names]
    return t


def _from_table(r) -> dict:
    return {"team": r.team, "kind": r.kind, "kind_label": KIND_LABEL.get(r.kind, r.kind),
            "founded_date": r.founded_date, "date_precision": r.date_precision,
            "founded_time": r.founded_time or None, "place": r.place,
            "lat": float(r.lat) if r.lat else None, "lon": float(r.lon) if r.lon else None,
            "country": r.country, "source": r.source, "sitelinks": int(r.sitelinks or 0) if hasattr(r, "sitelinks") else 0,
            "date_source": getattr(r, "date_source", "") or "wikidata"}


def search(q: str, con=None, limit: int = 8) -> list[dict]:
    """Candidates for a typed team name, best first. Each has a `match` of exact / alias / close."""
    k = _key(q)
    if not k:
        return []
    out = []
    if con is not None:
        from . import db
        for r in db.team_charts(con):
            if _key(r["team"]) == k:
                out.append({**dict(r), "kind": "manual", "kind_label": KIND_LABEL["manual"],
                            "source": "manual", "match": "exact"})
    t = table()
    if len(t):
        exact = t[[k == _key(team) for team in t.team]]
        alias = t[[k in keys and k != _key(team) for keys, team in zip(t["keys"], t.team)]]
        for df, how in ((exact, "exact"), (alias, "alias")):
            out += [{**_from_table(r), "match": how} for r in df.itertuples()]
        if len(out) < limit:
            # close spellings: "Man United" -> "Manchester United", "Inter" -> "Inter Milan", ...
            pool = {key: i for i, keys in zip(t.index, t["keys"]) for key in keys}
            close = difflib.get_close_matches(k, list(pool), n=limit * 2, cutoff=0.75)
            close += [key for key in pool if key.startswith(k + " ") or (" " + k) in key][:limit]
            seen = {(o["team"], o["kind"]) for o in out}
            for key in close:
                r = t.loc[pool[key]]
                if (r.team, r.kind) not in seen:
                    out.append({**_from_table(r), "match": "close"})
                    seen.add((r.team, r.kind))
    # Your saved charts first; then name matches (exact and alias alike) by prominence = number of
    # Wikipedia language editions, so "Arsenal" finds Arsenal F.C. before Arsenal of Maseru.
    tier = {"manual": 0}
    rank = {"exact": 1, "alias": 1, "close": 2}
    out.sort(key=lambda o: (tier.get(o["kind"], rank[o["match"]]), -int(o.get("sitelinks") or 0),
                            {"nation": 0, "club": 1, "national_team": 2}.get(o["kind"], 3)))
    return out[:limit]


DOMINANCE = 3.0   # auto-fill only if the top name match has this many times the next one's prominence


def best(q: str, con=None) -> dict | None:
    """The record to auto-fill, or None when the name is ambiguous (the form then offers a dropdown)."""
    allc = search(q, con, limit=8)
    c = [x for x in allc if x["match"] in ("exact", "alias")]
    if not c:
        return None
    if c[0]["kind"] == "manual":
        return c[0]
    top = int(c[0].get("sitelinks") or 0)
    # other teams with the same name must be clearly less prominent ...
    same_name = [int(x.get("sitelinks") or 0) for x in c[1:]]
    if same_name and top < DOMINANCE * max(max(same_name), 1):
        return None
    # ... and no merely similar name may be more prominent than the exact match: "Boca Juniors" the
    # Gibraltar club vs Club Atlético Boca Juniors. Less prominent look-alikes (Armenia for "Argentina",
    # AJ Auxerre for "Ajax") do not block.
    if any(int(x.get("sitelinks") or 0) > top for x in allc if x["match"] == "close"):
        return None
    return c[0]


def usable(rec: dict) -> tuple[bool, str]:
    if not rec.get("founded_date"):
        return False, "no founding date"
    if rec.get("date_precision") not in (None, "", "day"):
        return False, f"founding date known only to the {rec['date_precision']}: the Moon cannot be placed"
    if rec.get("lat") is None or rec.get("lon") is None:
        return False, "founding place has no coordinates"
    return True, ""


def _local_tz(lat, lon):
    tz = geo.timezone_at(lat, lon)
    if tz:
        return ZoneInfo(tz)            # zoneinfo applies historical offsets (e.g. local mean time pre-1880s)
    return timezone(timedelta(hours=round(lon / 15 * 4) / 4))   # fallback: solar time by longitude


def cast(rec: dict) -> tuple[dict | None, dict]:
    """Founding chart for a record. Returns (raw chart or None, meta) where meta explains precision."""
    ok, why = usable(rec)
    if not ok:
        return None, {"usable": False, "reason": why}
    d = datetime.fromisoformat(rec["founded_date"]).date()
    tz = _local_tz(rec["lat"], rec["lon"])
    t_known = bool(rec.get("founded_time"))
    t = time.fromisoformat(rec["founded_time"]) if t_known else time(12, 0)
    local = datetime.combine(d, t, tzinfo=tz)
    rc = ephem.raw_chart(ephem.jd_utc(local), rec["lat"], rec["lon"], with_hours=False)
    rc["time_known"] = t_known
    meta = {"usable": True, "time_known": t_known, "local": local.strftime("%Y-%m-%d %H:%M %Z").strip()}
    if not t_known:
        # Is the (sidereal) Moon in the same sign all day? If not, its sign is genuinely uncertain.
        signs = set()
        for hh in (0, 23):
            m = datetime.combine(d, time(hh, 59 if hh else 0), tzinfo=tz)
            r = ephem.raw_chart(ephem.jd_utc(m), rec["lat"], rec["lon"], with_hours=False)
            signs.add(ephem.sign_of(r["blon"][1] - r["ayan_lahiri"]))
        rc["moon_sign_certain"] = len(signs) == 1
        meta["moon_sign_certain"] = rc["moon_sign_certain"]
    return rc, meta
