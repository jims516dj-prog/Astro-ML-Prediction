"""ESPN's public tennis scoreboard (no key): singles matches with set-by-set scores, seeds and players,
plus each player's date and place of birth. Unofficial feed: if it changes, the build and cycle stop
cleanly and say so."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import date

API = "https://site.api.espn.com/apis/site/v2/sports/tennis"
CORE = "https://sports.core.api.espn.com/v2/sports/tennis/athletes"
UA = "astro-football-research/1.0 (tennis; contact via repository)"
TOURS = ("atp", "wta")
SINGLES = {"Men's Singles": "atp", "Women's Singles": "wta"}


def get_json(url: str, tries: int = 3) -> dict:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404) or i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(2 * (i + 1))
    return {}


def scoreboard(tour: str, d_from: date, d_to: date | None = None, get=get_json) -> list[dict]:
    q = f"{d_from:%Y%m%d}" + (f"-{d_to:%Y%m%d}" if d_to and d_to != d_from else "")
    return get(f"{API}/{tour}/scoreboard?dates={q}").get("events", [])


# "(8) Linda Noskova (CZE) bt (9) Marta Kostyuk (UKR) 6-2 6-4", "(Q) A (USA) bt (WC) B (FRA) ..."
_ENTRY = re.compile(r"((?:\(\s*[0-9A-Za-z]+\s*\)\s*)*)([^()]+?)\s*\(([A-Za-z]{3})\)")


def _entries(note: str) -> dict[str, dict]:
    out = {}
    for tags, name, _cc in _ENTRY.findall(note or ""):
        name = re.sub(r"^\s*(bt|def\.?|d\.)\s+", "", name.strip())
        seed, entry = None, None
        for t in re.findall(r"\(\s*([0-9A-Za-z]+)\s*\)", tags):
            if t.isdigit():
                seed = int(t)
            elif t.upper() in ("Q", "WC", "LL", "PR", "SE", "ALT"):
                entry = t.upper()
        out[_key(name)] = {"seed": seed, "entry": entry}
    return out


def _key(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def parse_event(e: dict) -> list[dict]:
    """Singles matches of one ESPN tournament event (both tours where a Grand Slam lists both draws)."""
    rows = []
    for g in e.get("groupings") or []:
        tour = SINGLES.get(((g.get("grouping") or {}).get("displayName") or "").strip())
        if not tour:
            continue
        for c in g.get("competitions") or []:
            r = parse_competition(c, e, tour)
            if r:
                rows.append(r)
    return rows


def parse_competition(c: dict, e: dict, tour: str) -> dict | None:
    comps = c.get("competitors") or []
    if len(comps) != 2 or any(x.get("type") != "athlete" or not x.get("athlete") for x in comps):
        return None
    comps = sorted(comps, key=lambda x: x.get("order", 0))
    st = (c.get("status") or {}).get("type") or {}
    note = " ".join(n.get("text", "") for n in c.get("notes") or [])
    low = note.lower()
    ent = _entries(note)
    p = []
    for x in comps:
        a = x["athlete"]
        name = a.get("displayName") or a.get("fullName") or ""
        info = ent.get(_key(name), {})
        p.append({"id": str(x.get("id") or ""), "name": name, "country": (a.get("flag") or {}).get("alt") or "",
                  "seed": info.get("seed"), "entry": info.get("entry"),
                  "rank": ((x.get("curatedRank") or {}).get("current")), "winner": bool(x.get("winner")),
                  "sets": [(float(s.get("value") or 0), s.get("winner")) for s in x.get("linescores") or []]})
    n_sets = min(len(p[0]["sets"]), len(p[1]["sets"]))
    set_winners = []
    for i in range(n_sets):
        a, b = p[0]["sets"][i], p[1]["sets"][i]
        if a[1] is True or b[1] is False and a[0] > b[0]:
            set_winners.append(1)
        elif b[1] is True or a[1] is False and b[0] > a[0]:
            set_winners.append(2)
        elif a[0] != b[0]:
            set_winners.append(1 if a[0] > b[0] else 2)
    score = " ".join(f"{int(p[0]['sets'][i][0])}-{int(p[1]['sets'][i][0])}" for i in range(n_sets))
    walkover = "w/o" in low or "walkover" in low or (st.get("completed") and n_sets == 0)
    retired = ("ret" in low and "retir" in low) or " ret." in low or "ret)" in low or st.get("name") == "STATUS_RETIRED"
    winner = 1 if p[0]["winner"] else 2 if p[1]["winner"] else None
    venue = (c.get("venue") or {}).get("fullName") or ""
    return {
        "id": str(c.get("id")), "event_id": str(e.get("id") or ""), "event": e.get("name") or "", "tour": tour,
        "date": c.get("date") or c.get("startDate") or e.get("date"), "venue": venue,
        "round": ((c.get("round") or {}).get("displayName") or ""),
        "best_of": best_of(tour, e.get("name") or "", ((c.get("round") or {}).get("displayName") or "")),
        "state": st.get("state") or "", "status": st.get("name") or "", "completed": bool(st.get("completed")),
        "time_valid": c.get("timeValid"),
        "p1_id": p[0]["id"], "p1": p[0]["name"], "p1_country": p[0]["country"], "p1_seed": p[0]["seed"],
        "p1_entry": p[0]["entry"], "p1_rank": p[0]["rank"],
        "p2_id": p[1]["id"], "p2": p[1]["name"], "p2_country": p[1]["country"], "p2_seed": p[1]["seed"],
        "p2_entry": p[1]["entry"], "p2_rank": p[1]["rank"],
        "winner": winner, "score": score, "set_winners": "".join(map(str, set_winners)),
        "retired": bool(retired) and not walkover, "walkover": bool(walkover), "note": note[:300],
    }


SLAMS = ("australian open", "french open", "roland garros", "wimbledon", "us open")


def best_of(tour: str, event: str, round_name: str) -> int:
    """ESPN reports 5 'periods' for every ATP match, so the format is derived: best of 5 only in the men's
    Grand Slam main draws (qualifying is best of 3)."""
    ev, rd = (event or "").lower(), (round_name or "").lower()
    return 5 if tour == "atp" and any(x in ev for x in SLAMS) and "qualif" not in rd else 3


def athlete(pid: str, get=get_json) -> dict:
    """Date and place of birth, hand and height of one player."""
    d = get(f"{CORE}/{pid}")
    dob = (d.get("dateOfBirth") or "")[:10] or None
    return {"id": str(pid), "name": d.get("displayName") or d.get("fullName") or "", "full_name": d.get("fullName") or "",
            "dob": dob, "birthplace": (d.get("birthPlace") or {}).get("summary") or "",
            "hand": ((d.get("hand") or {}).get("abbreviation") or ""), "height_in": d.get("height"),
            "country": (d.get("flag") or {}).get("alt") or ""}
