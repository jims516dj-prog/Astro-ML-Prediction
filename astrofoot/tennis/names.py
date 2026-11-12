"""Players' full legal (birth) names for name numerology, from data/ref/tennis_names.json (written by
scripts/fetch_tennis_names.py). On screen players keep the name their tour lists them under."""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from ..config import ROOT

FILE = ROOT / "data" / "ref" / "tennis_names.json"


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def reload() -> None:
    _table.cache_clear()


def legal(pid) -> str | None:
    return (_table().get(str(pid)) or {}).get("legal")


def apply(players: pd.DataFrame) -> pd.DataFrame:
    """full_name (read by the numerology) set to the legal name where it is known; name (shown) unchanged."""
    t = _table()
    if players is None or players.empty or not t:
        return players
    pl = players.copy()
    got = pl["id"].astype(str).map(lambda i: (t.get(i) or {}).get("legal"))
    pl["full_name"] = got.where(got.notna(), pl["full_name"])
    return pl
