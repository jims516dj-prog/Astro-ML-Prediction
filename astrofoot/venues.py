"""Venue -> coordinates (spec §3.2): saved venues, offline stadium/city tables, Wikipedia,
Nominatim, and always a manual override in the form."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

from . import geo
from .config import RAW

UA = "astro-football-research/1.0 (local research instrument)"
DISAMBIG = {"old trafford": "Old Trafford", "camp nou": "Camp Nou", "anfield": "Anfield",
            "wembley": "Wembley Stadium", "san siro": "San Siro"}


def _get(url, timeout=3.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wikipedia(name: str):
    title = DISAMBIG.get(name.lower().strip(), name)
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "coordinates",
                                "titles": title, "redirects": 1})
    data = _get(f"https://en.wikipedia.org/w/api.php?{q}")
    for page in data.get("query", {}).get("pages", {}).values():
        coords = page.get("coordinates") or []
        primary = [c for c in coords if c.get("primary") is not None] or coords
        if primary:
            return float(primary[0]["lat"]), float(primary[0]["lon"]), page.get("title")
    return None


GROUND_WORDS = ("stadium", "stadion", "stadio", "estadio", "estádio", "stade", "arena", "park", "ground", "field",
                "parken", "anfield", "dome", "bowl", "kombëtar", "stadionul", "stadiumi", "štadión", "stadyum")


def wikipedia_ground(club: str):
    """A club's home ground via Wikipedia search ("<club> stadium"): the first hit that has coordinates and
    whose title names a ground. Returns (lat, lon, title) or None."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrlimit": 6,
                                "gsrsearch": f"{club} stadium football", "prop": "coordinates", "redirects": 1})
    data = _get(f"https://en.wikipedia.org/w/api.php?{q}", timeout=8.0)
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for page in pages:
        coords = page.get("coordinates") or []
        if coords and any(w in page.get("title", "").lower() for w in GROUND_WORDS):
            return float(coords[0]["lat"]), float(coords[0]["lon"]), page["title"]
    return None


def nominatim_ground(club: str):
    """OpenStreetMap search for the club, accepting only a sports ground (leisure=stadium/pitch/sports_centre)."""
    for query in (f"{club} stadium", club):
        q = urllib.parse.urlencode({"q": query, "format": "json", "limit": 8})
        for hit in _get(f"https://nominatim.openstreetmap.org/search?{q}", timeout=8.0) or []:
            if hit.get("type") in ("stadium", "pitch", "sports_centre") or hit.get("class") == "leisure" and \
                    hit.get("type") == "stadium":
                return float(hit["lat"]), float(hit["lon"]), hit.get("display_name")
    return None


def nominatim_stadium(query: str):
    """OpenStreetMap search for a named ground (e.g. "Hayes Lane, Bromley"), sports grounds only."""
    q = urllib.parse.urlencode({"q": query, "format": "json", "limit": 8})
    for hit in _get(f"https://nominatim.openstreetmap.org/search?{q}", timeout=8.0) or []:
        if hit.get("type") in ("stadium", "pitch", "sports_centre"):
            return float(hit["lat"]), float(hit["lon"]), hit.get("display_name")
    return None


def km(a, b) -> float:
    """Great-circle distance in km between (lat, lon) pairs."""
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def nominatim(name: str):
    q = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
    data = _get(f"https://nominatim.openstreetmap.org/search?{q}")
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name")
    return None


def offline(name: str):
    if not (RAW / "stadiums.csv").exists():      # tables not downloaded: python scripts/fetch_data.py --live
        return None
    s = pd.read_csv(RAW / "stadiums.csv", encoding="latin-1")
    key = geo.norm(name)
    for r in s.itertuples():
        if key in (geo.norm(r.Stadium), geo.norm(r.Team), geo.norm(str(r.FDCOUK))):
            return float(r.Latitude), float(r.Longitude), f"{str(r.Stadium).strip()} ({str(r.City).strip()})"
    if not (RAW / "csv-cities.csv.gz").exists():
        return None
    c = geo.cities()
    hit = c[c.key == key]
    if len(hit):
        h = hit.iloc[0]
        return float(h.latitude), float(h.longitude), f"{h['name']}, {h.country_code} (city centre)"
    return None


def lookup(name: str, con=None) -> dict:
    """Returns {lat, lon, source, label, notes[]}; never raises."""
    notes = []
    if con is not None:
        from . import db
        v = db.find_venue(con, name)
        if v:
            return {"lat": v["lat"], "lon": v["lon"], "source": v["source"], "label": v["name"],
                    "notes": [f"saved venue (verified {v['verified_at']})"]}
    for fn, src in ((wikipedia, "wikipedia"), (nominatim, "openstreetmap")):
        try:
            r = fn(name)
            if r:
                return {"lat": r[0], "lon": r[1], "source": src, "label": r[2], "notes": notes}
            notes.append(f"{src}: no coordinates found")
        except Exception as e:  # network blocked, timeout, bad JSON
            notes.append(f"{src} unavailable ({type(e).__name__})")
    r = offline(name)
    if r:
        return {"lat": r[0], "lon": r[1], "source": "offline table", "label": r[2], "notes": notes}
    notes.append("Lookup unavailable — please enter coordinates manually.")
    return {"lat": None, "lon": None, "source": None, "label": None, "notes": notes}
