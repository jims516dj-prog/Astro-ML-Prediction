"""Pre-match features for a tennis match, built in time order so nothing uses information from after the
match: statistics (Elo overall and by surface, form, sets form, rest, workload, head-to-head, seeds,
entry, age, height, hand, home country, format), astrology and numerology (astro_num)."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from . import astro_num as an
from . import daychart as dc
from . import espn

STAT_FEATURES = ["elo_diff", "selo_diff", "blend_diff", "p_elo", "n_diff", "a_n_log", "b_n_log", "form_diff",
                 "a_form", "b_form", "setform_diff", "a_rest", "b_rest", "load_diff", "h2h_diff", "h2h_n",
                 "a_seed_inv", "b_seed_inv", "a_q", "b_q", "a_wc", "b_wc", "age_diff", "a_age", "b_age",
                 "height_diff", "a_left", "b_left", "a_home", "b_home", "best_of5", "slam", "qualifying",
                 "round_no", "surf_clay", "surf_grass", "tour_wta"]
# date-only astrology and numerology (daychart): A − B differences of every contact / number, and the
# traditional day scores of each player
ASTRO = [f"d_astro_{k}" for k in dc.FEATURES] + ["a_astro_rule", "b_astro_rule", "d_astro_rule"]
NUMER = [f"d_num_{k}" for k in dc.NUM_FEATURES] + ["a_num_rule", "b_num_rule", "d_num_rule"]
GROUPS = {"stats": STAT_FEATURES, "astro": ASTRO, "numerology": NUMER}
SLAMS = ("australian open", "french open", "roland garros", "wimbledon", "us open")
ROUNDS = {"final": 7, "semifinal": 6, "quarterfinal": 5, "round of 16": 4, "4th round": 4, "fourth round": 4,
          "3rd round": 3, "third round": 3, "round 3": 3, "2nd round": 2, "second round": 2, "round 2": 2,
          "1st round": 1, "first round": 1, "round 1": 1}


PLACEHOLDER_NAMES = {"TBD", "TBA", "BYE", "QUALIFIER", "LUCKY LOSER", "WINNER", "LOSER"}


def placeholder(pid, name) -> bool:
    """ESPN's not-yet-known players: 'TBD' (a qualifier still to come, …), with negative ids."""
    return (not pid or str(pid).startswith("-") or str(name or "").strip().upper() in PLACEHOLDER_NAMES
            or str(name or "").strip().upper().startswith("TBD"))


def round_no(name: str) -> int:
    n = (name or "").lower()
    if "qualif" in n:
        return 0
    for k, v in ROUNDS.items():
        if k in n:
            return v
    return 2


def k_factor(n: int) -> float:
    return 250.0 / (n + 5) ** 0.4


@dataclass
class State:
    elo: dict = field(default_factory=lambda: defaultdict(lambda: 1500.0))
    selo: dict = field(default_factory=lambda: defaultdict(lambda: 1500.0))
    n: dict = field(default_factory=lambda: defaultdict(int))
    sn: dict = field(default_factory=lambda: defaultdict(int))
    form: dict = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=10)))
    setform: dict = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=30)))
    last: dict = field(default_factory=dict)
    recent: dict = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=20)))
    h2h: dict = field(default_factory=lambda: defaultdict(int))
    names: dict = field(default_factory=dict)

    def update(self, m: dict):
        """Learn from one completed match (not walkovers; retirements only for workload)."""
        a, b, when = m["p1_id"], m["p2_id"], m["date"]
        if placeholder(a, m.get("p1")) or placeholder(b, m.get("p2")):
            return
        for p in (a, b):
            self.last[p] = when
            self.recent[p].append(when)
        self.names[a], self.names[b] = m["p1"], m["p2"]
        if m.get("walkover") or m.get("retired") or m.get("winner") not in (1, 2):
            return
        s = 1.0 if m["winner"] == 1 else 0.0
        surf = m.get("surface", "hard")
        ea = 1 / (1 + 10 ** ((self.elo[b] - self.elo[a]) / 400))
        ka, kb = k_factor(self.n[a]), k_factor(self.n[b])
        self.elo[a] += ka * (s - ea)
        self.elo[b] -= kb * (s - ea)
        sa, sb = (a, surf), (b, surf)
        es = 1 / (1 + 10 ** ((self.selo[sb] - self.selo[sa]) / 400))
        ksa, ksb = k_factor(self.sn[sa]), k_factor(self.sn[sb])
        self.selo[sa] += ksa * (s - es)
        self.selo[sb] -= ksb * (s - es)
        self.n[a] += 1
        self.n[b] += 1
        self.sn[sa] += 1
        self.sn[sb] += 1
        self.form[a].append(s)
        self.form[b].append(1 - s)
        for w in str(m.get("set_winners") or ""):
            self.setform[a].append(1.0 if w == "1" else 0.0)
            self.setform[b].append(1.0 if w == "2" else 0.0)
        self.h2h[(a, b)] += int(s == 1)
        self.h2h[(b, a)] += int(s == 0)


def _age(dob, when) -> float:
    dob = an.clean_dob(dob)
    if not dob:
        return np.nan
    return (when - pd.Timestamp(dob, tz="UTC")).days / 365.25


def _country(venue: str) -> str:
    return (venue or "").split(",")[-1].strip().lower()


ALIASES = {"usa": "united states", "united states of america": "united states", "great britain": "united kingdom",
           "england": "united kingdom", "uk": "united kingdom", "czech republic": "czechia", "korea": "south korea"}


def _same_country(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    a, b = ALIASES.get(a, a), ALIASES.get(b, b)
    return float(bool(a) and a == b)


def row(st: State, m: dict, players: dict) -> dict:
    """Features of match m with player 1 as A and player 2 as B, from the state before the match."""
    a, b, when = m["p1_id"], m["p2_id"], m["date"]
    surf = m.get("surface", "hard")
    pa, pb = players.get(a, {}), players.get(b, {})
    blend_a = 0.5 * st.elo[a] + 0.5 * st.selo[(a, surf)]
    blend_b = 0.5 * st.elo[b] + 0.5 * st.selo[(b, surf)]
    fa, fb = st.form[a], st.form[b]
    sfa, sfb = st.setform[a], st.setform[b]
    rest = lambda p: min(60.0, (when - st.last[p]).total_seconds() / 86400) if p in st.last else 60.0  # noqa: E731
    load = lambda p: sum(1 for t in st.recent[p] if (when - t).days <= 14)                             # noqa: E731
    seed_inv = lambda s: 0.0 if s is None or pd.isna(s) else 1.0 / float(s)                            # noqa: E731
    ev = (m.get("event") or "").lower()
    venue_c = _country(m.get("venue"))
    hw = lambda p: float(str(p.get("hand", "")).upper() == "L")                                         # noqa: E731
    h = lambda p: float(p.get("height_in")) if p.get("height_in") not in (None, "") and not pd.isna(p.get("height_in")) else np.nan  # noqa: E731
    age_a, age_b = _age(pa.get("dob"), when), _age(pb.get("dob"), when)
    out = {
        "elo_diff": st.elo[a] - st.elo[b], "selo_diff": st.selo[(a, surf)] - st.selo[(b, surf)],
        "blend_diff": blend_a - blend_b, "p_elo": 1 / (1 + 10 ** ((blend_b - blend_a) / 400)),
        "n_diff": np.log1p(st.n[a]) - np.log1p(st.n[b]), "a_n_log": np.log1p(st.n[a]), "b_n_log": np.log1p(st.n[b]),
        "a_form": np.mean(fa) if fa else 0.5, "b_form": np.mean(fb) if fb else 0.5,
        "setform_diff": (np.mean(sfa) if sfa else 0.5) - (np.mean(sfb) if sfb else 0.5),
        "a_rest": rest(a), "b_rest": rest(b), "load_diff": load(a) - load(b),
        "h2h_diff": st.h2h[(a, b)] - st.h2h[(b, a)], "h2h_n": st.h2h[(a, b)] + st.h2h[(b, a)],
        "a_seed_inv": seed_inv(m.get("p1_seed")), "b_seed_inv": seed_inv(m.get("p2_seed")),
        "a_q": float(m.get("p1_entry") in ("Q", "LL")), "b_q": float(m.get("p2_entry") in ("Q", "LL")),
        "a_wc": float(m.get("p1_entry") == "WC"), "b_wc": float(m.get("p2_entry") == "WC"),
        "a_age": age_a, "b_age": age_b, "age_diff": age_a - age_b,
        "height_diff": h(pa) - h(pb), "a_left": hw(pa), "b_left": hw(pb),
        "a_home": _same_country(m.get("p1_country") or pa.get("country"), venue_c),
        "b_home": _same_country(m.get("p2_country") or pb.get("country"), venue_c),
        "best_of5": float(espn.best_of(m.get("tour"), m.get("event"), m.get("round")) == 5),
        "slam": float(any(s in ev for s in SLAMS)),
        "qualifying": float("qualif" in (m.get("round") or "").lower()), "round_no": float(round_no(m.get("round"))),
        "surf_clay": float(surf == "clay"), "surf_grass": float(surf == "grass"), "tour_wta": float(m.get("tour") == "wta"),
    }
    out["form_diff"] = out["a_form"] - out["b_form"]
    out.update(day_features(pa, pb, m["p1"], m["p2"], when))
    return out


def day_features(pa: dict, pb: dict, name_a: str, name_b: str, when) -> dict:
    """Date-only astrology and numerology of both players for the match day (see daychart)."""
    day = str(when)[:10] if not hasattr(when, "strftime") else when.strftime("%Y-%m-%d")
    out = {}
    va, vb = dc.contact_vector(pa.get("dob"), day), dc.contact_vector(pb.get("dob"), day)
    for k, x in zip(dc.FEATURES, va - vb):
        out[f"d_astro_{k}"] = float(x)
    ra, rb = dc.astro_day(pa.get("dob"), day)["score"], dc.astro_day(pb.get("dob"), day)["score"]
    out.update(a_astro_rule=np.nan if ra is None else ra, b_astro_rule=np.nan if rb is None else rb)
    out["d_astro_rule"] = out["a_astro_rule"] - out["b_astro_rule"]
    na = dc.num_vector(pa.get("dob"), pa.get("full_name") or name_a, day)
    nb = dc.num_vector(pb.get("dob"), pb.get("full_name") or name_b, day)
    for k, x in zip(dc.NUM_FEATURES, na - nb):
        out[f"d_num_{k}"] = float(x)
    sa = dc.num_day(pa.get("dob"), pa.get("full_name") or name_a, day)["score"]
    sb = dc.num_day(pb.get("dob"), pb.get("full_name") or name_b, day)["score"]
    out.update(a_num_rule=np.nan if sa is None else sa, b_num_rule=np.nan if sb is None else sb)
    out["d_num_rule"] = out["a_num_rule"] - out["b_num_rule"]
    return out


def players_dict(pl: pd.DataFrame) -> dict:
    if pl is None or pl.empty:
        return {}
    return {str(r["id"]): r for r in pl.to_dict("records")}


def usable(m: dict) -> bool:
    return bool(m.get("completed")) and not m.get("walkover") and m.get("winner") in (1, 2) \
        and bool(m.get("set_winners"))


def history(matches: pd.DataFrame, players: pd.DataFrame, since: str | None = "2012-01-01",
            log=lambda *a: None) -> tuple[pd.DataFrame, State]:
    """Feature rows for every usable completed match (from `since`, after a warm-up for the ratings) and
    the final state. Each row carries its labels: winner, set winners, retired."""
    st, pd_ = State(), players_dict(players)
    rows = []
    cut = pd.Timestamp(since, tz="UTC") if since else None
    ms = matches.sort_values(["date", "id"]).to_dict("records")
    for i, m in enumerate(ms):
        if not m.get("completed"):
            continue
        if usable(m) and not m.get("retired") and (cut is None or m["date"] >= cut):
            f = row(st, m, pd_)
            f.update(id=m["id"], date=m["date"], tour=m["tour"], surface=m.get("surface"), best_of=m.get("best_of"),
                     winner=m["winner"], set_winners=m["set_winners"], p1=m["p1"], p2=m["p2"], event=m["event"])
            rows.append(f)
        st.update(m)
        if i % 20000 == 0:
            log(f"  features {i}/{len(ms)}")
    return pd.DataFrame(rows), st


def flip(df: pd.DataFrame) -> pd.DataFrame:
    """The same matches seen from the other player (A↔B): differences change sign, a_/b_ columns swap."""
    f = df.copy()
    for c in ("elo_diff", "selo_diff", "blend_diff", "n_diff", "form_diff", "setform_diff", "load_diff", "h2h_diff",
              "age_diff", "height_diff"):
        if c in f:
            f[c] = -df[c]
    if "p_elo" in f:
        f["p_elo"] = 1 - df["p_elo"]
    for c in df.columns:
        if c.startswith("a_") and "b_" + c[2:] in df.columns:
            f[c], f["b_" + c[2:]] = df["b_" + c[2:]], df[c]
    for c in df.columns:
        if c.startswith("d_"):
            f[c] = -df[c]
    if "winner" in f:
        f["winner"] = 3 - df["winner"]
    if "set_winners" in f:
        f["set_winners"] = df["set_winners"].str.translate(str.maketrans("12", "21"))
    if "p1" in f:
        f["p1"], f["p2"] = df["p2"], df["p1"]
    return f
