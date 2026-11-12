"""Soccer: is the day favourable to a team, and to its scoring? Date-only astrology and numerology, as for tennis
players, with the club's founding date as its birth date (data/ref/team_foundings.csv; only dates known to the day).

- Astrology: the founding-date chart (planets at 12:00 UTC) against the sky on the match day at the venue (noon there).
  "Day" score: the traditional reading used for tennis (Jupiter / Venus contacts add, Saturn / hard Mars subtract).
  "Scoring" score: contacts tied to attack: Mars and Jupiter to the natal Mars and Sun add; Saturn to them subtracts.
- Numerology: personal day of the founding date and the club name. "Day" as for tennis; "scoring": active days
  (1, 3, 5, 8, 9) add, restrictive days (4, 7) subtract.
Research (scripts/research.py teamday) measures both on past matches against the odds; see data/models/teamday.json."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from .config import MODELS, REF
from .tennis import astro_num as an
from .tennis import daychart as dc

CACHE = REF / "team_founding_days.json"
RESEARCH = MODELS / "teamday.json"

# transit → natal (conjunction, harmonious, hard) weights for scoring
ATTACK_RULES = {
    ("Ma", "Ma"): (1.0, 1.0, -0.5), ("Ma", "Su"): (0.8, 0.8, -0.6), ("Ju", "Ma"): (1.2, 1.0, -0.3),
    ("Ju", "Su"): (0.8, 0.8, -0.3), ("Su", "Ma"): (0.6, 0.5, -0.3), ("Me", "Ma"): (0.3, 0.3, -0.2),
    ("Sa", "Ma"): (-1.2, 0.2, -1.2), ("Sa", "Su"): (-0.8, 0.2, -0.8), ("Ve", "Ma"): (0.3, 0.3, 0.0),
}
ACTIVE, RESTRICTIVE = {1, 3, 5, 8, 9}, {4, 7}


# ----------------------------------------------------------------------------- founding dates
_mem: dict | None = None


def _load() -> dict:
    global _mem
    if _mem is None:
        _mem = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    return _mem


def founding(team: str, con=None, resolve: bool = True) -> dict | None:
    """{'date', 'name'} of a team's founding (known to the day), or None. Name look-ups are slow, so every answer
    (found or not) is kept in data/ref/team_founding_days.json."""
    cache = _load()
    if team in cache:
        return cache[team]
    if not resolve:
        return None
    from . import foundings
    b = foundings.best(team, con)
    rec = None
    if b and b.get("founded_date") and b.get("date_precision") in (None, "", "day"):
        rec = {"date": str(b["founded_date"])[:10], "name": b.get("team") or team}
    cache[team] = rec
    try:
        CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))
    except OSError:
        pass
    return rec


# ----------------------------------------------------------------------------- readings
def attack_day(dob: str | None, day: str, tz: str | None = None) -> dict:
    dob = an.clean_dob(dob)
    if not dob:
        return {"score": None, "contacts": []}
    t, n = dc.sky(day, tz), dc.positions(dob)
    sep = dc._sep(t, n)
    score, why = 0.0, []
    for (tp, np_), w in ATTACK_RULES.items():
        i, j = dc.PLANETS.index(tp), dc.PLANETS.index(np_)
        for asp, fam in ((0, 0), (60, 1), (120, 1), (90, 2), (180, 2)):
            s = max(0.0, 1 - abs(sep[i, j] - asp) / dc.ORB)
            if s > 0 and w[fam]:
                score += w[fam] * s
                why.append({"text": f"{dc.NAMES[tp]} {dc.ASPECT_NAME[asp]} natal {dc.NAMES[np_]}",
                            "points": round(float(w[fam] * s), 2), "orb": round(float(abs(sep[i, j] - asp)), 1)})
    why.sort(key=lambda x: -abs(x["points"]))
    return {"score": round(float(score), 3), "contacts": why}


def num_attack(dob: str | None, day: str) -> dict:
    dob = an.clean_dob(dob)
    if not dob:
        return {"score": None, "parts": []}
    pd_ = an.personal_day(dob, date.fromisoformat(day[:10]))
    parts = []
    if pd_ in ACTIVE:
        parts.append((f"Personal day {pd_}: an active, expressive number", 1.0))
    if pd_ in RESTRICTIVE:
        parts.append((f"Personal day {pd_}: a restrictive number", -0.75))
    if pd_ == an.reduce(an.life_path(dob)):
        parts.append(("Personal day equals the founding life path", 0.5))
    return {"score": round(sum(p for _, p in parts), 2), "parts": [{"text": t, "points": p} for t, p in parts]}


@lru_cache(maxsize=200000)
def _team_day(dob: str, name: str, day: str, tz: str | None) -> dict:
    return {"astro": dc.astro_day(dob, day, tz), "attack": attack_day(dob, day, tz),
            "num": dc.num_day(dob, name, day), "num_attack": num_attack(dob, day)}


def reading(home: str, away: str, kickoff_utc, lat=None, lon=None, con=None, resolve: bool = True) -> dict:
    """Both teams' day and scoring readings for a match, and who each reading favours."""
    from . import geo
    from .tennis.venue import _dt
    from zoneinfo import ZoneInfo
    tz = None
    try:
        tz = geo.timezone_at(float(lat), float(lon)) if lat is not None and lon is not None else None
    except Exception:  # noqa: BLE001
        tz = None
    w = _dt(kickoff_utc)
    day = (w.astimezone(ZoneInfo(tz)) if tz else w).strftime("%Y-%m-%d")
    out = {"day": day, "tz": tz}
    for side, team in (("home", home), ("away", away)):
        f = founding(team, con, resolve)
        r = _team_day(f["date"], f["name"], day, tz) if f else None
        out[side] = {"team": team, "founded": f["date"] if f else None, "chart_name": f["name"] if f else None,
                     **(r or {"astro": {"score": None, "contacts": []}, "attack": {"score": None, "contacts": []},
                              "num": {"score": None, "parts": [], "numbers": {}}, "num_attack": {"score": None, "parts": []}})}
    h, a = out["home"], out["away"]
    out["favours"] = {"astro": dc.verdict(h["astro"]["score"], a["astro"]["score"]),
                      "num": dc.verdict(h["num"]["score"], a["num"]["score"], 0.4)}
    # scoring: each team on its own (a day can favour both teams to score)
    for side in ("home", "away"):
        x = out[side]
        x["score_astro"] = _lean(x["attack"]["score"], 0.25)
        x["score_num"] = _lean(x["num_attack"]["score"], 0.5)
    return out


def _lean(v, margin) -> int:
    """+1 favourable, -1 unfavourable, 0 neutral or unknown."""
    if v is None:
        return 0
    return 1 if v > margin else -1 if v < -margin else 0


def research() -> dict:
    return json.loads(RESEARCH.read_text()) if RESEARCH.exists() else {}
