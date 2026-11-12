"""One id per player. ESPN sometimes lists the same player under two ids (many were re-keyed in 2021-22), which
splits their ratings, form and head-to-head. Ids sharing exactly the same name are merged when their dates of birth
agree (or one is missing); real namesakes (different dates of birth) stay apart."""
from __future__ import annotations

import pandas as pd

from . import astro_num as an


def aliases(matches: pd.DataFrame, players: pd.DataFrame) -> dict[str, str]:
    """{duplicate id: id kept}. The kept id is the one with a date of birth and the most matches."""
    if matches.empty:
        return {}
    x = pd.concat([matches[["p1_id", "p1"]].set_axis(["id", "name"], axis=1),
                   matches[["p2_id", "p2"]].set_axis(["id", "name"], axis=1)])
    x = x[~x.id.astype(str).str.startswith("-") & (x.id.astype(str) != "")]
    counts = x.groupby(["name", "id"]).size().reset_index(name="n")
    multi = counts[counts.duplicated("name", keep=False)]
    if multi.empty:
        return {}
    dob = {str(r["id"]): an.clean_dob(r.get("dob")) for r in players.to_dict("records")} if len(players) else {}
    out = {}
    for name, g in multi.groupby("name"):
        ids = [(str(i), int(n), dob.get(str(i))) for i, n in zip(g.id, g.n)]
        dobs = {d for _, _, d in ids if d}
        if len(dobs) > 1:          # real namesakes: leave them apart
            continue
        keep = max(ids, key=lambda t: (t[2] is not None, t[1]))[0]
        for i, _, _ in ids:
            if i != keep:
                out[i] = keep
    return out


def apply(matches: pd.DataFrame, alias: dict[str, str]) -> pd.DataFrame:
    if not alias or matches.empty:
        return matches
    m = matches.copy()
    m["p1_id"] = m["p1_id"].astype(str).replace(alias)
    m["p2_id"] = m["p2_id"].astype(str).replace(alias)
    return m
