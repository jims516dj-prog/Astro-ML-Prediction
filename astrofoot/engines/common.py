"""Shared chart view and verdict container for the classical engines."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import ephem
from ..tables import (BODIES, DEBIL, EXALT, MEAN_SPEED, MOOLATRIKONA, NAK_LORD, OWN_SIGNS,
                      RULER)


class View:
    """One raw chart seen through a zodiac (tropical/lahiri/kp) and a house system."""

    def __init__(self, rc: dict, zodiac: str, houses: str):
        self.rc = rc
        self.zodiac = zodiac
        self.ayan = 0.0 if zodiac == "tropical" else rc[f"ayan_{zodiac}"]
        lon = ephem.norm360(rc["blon"] - self.ayan)
        self.lon = {b: float(lon[i]) for i, b in enumerate(BODIES)}
        self.lon["Ke"] = float(ephem.norm360(self.lon["Ra"] + 180))
        self.spd = {b: float(rc["bspd"][i]) for i, b in enumerate(BODIES)}
        self.spd["Ke"] = self.spd["Ra"]
        self.asc = float(ephem.norm360(rc["asc"] - self.ayan))
        self.mc = float(ephem.norm360(rc["mc"] - self.ayan))
        self.cusps = ephem.cusps_for(rc, houses, self.ayan)
        # Part of Fortune: Asc + Moon - Sun, never reversed at night (Frawley)
        self.pof = float(ephem.norm360(self.asc + self.lon["Mo"] - self.lon["Su"]))

    # --- basic predicates -------------------------------------------------
    def sign(self, p: str) -> int:
        return ephem.sign_of(self.lon[p])

    def house(self, p: str) -> int:
        return ephem.house_of(self.lon[p], self.cusps)

    def cusp_sign(self, h: int) -> int:
        return ephem.sign_of(self.cusps[h - 1])

    def lord(self, h: int) -> str:
        return RULER[self.cusp_sign(h)]

    def retro(self, p: str) -> bool:
        return self.spd[p] < 0 and p not in ("Ra", "Ke")

    def exalted(self, p: str) -> bool:
        return EXALT.get(p) == self.sign(p)

    def debilitated(self, p: str) -> bool:
        return DEBIL.get(p) == self.sign(p)

    def own_sign(self, p: str) -> bool:
        return self.sign(p) in OWN_SIGNS.get(p, []) or MOOLATRIKONA.get(p) == self.sign(p)

    def own_nakshatra(self, p: str) -> bool:
        return NAK_LORD[ephem.nakshatra(self.lon[p])[0]] == p

    def station_ratio(self, p: str) -> float:
        return abs(self.spd[p]) / MEAN_SPEED.get(p, 1.0)

    def moon_phase(self) -> float:
        return float(ephem.norm360(self.lon["Mo"] - self.lon["Su"]))

    def occupants(self, h: int) -> list[str]:
        return [p for p in list(self.lon) if self.house(p) == h]


@dataclass
class Testimony:
    text: str
    side: str            # "fav" | "dog"
    points: float
    key: str             # stable doctrine key (used by the Doctrine Tribunal)


@dataclass
class Verdict:
    engine: str
    winner: str                      # "fav" | "dog" | "draw" | "disabled"
    score_fav: float = 0.0
    score_dog: float = 0.0
    goals_fav: int | None = None
    goals_dog: int | None = None
    confidence: str = "low"
    testimonies: list[Testimony] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    table: list[dict] = field(default_factory=list)
    features: dict = field(default_factory=dict)

    @property
    def net(self) -> float:
        return self.score_fav - self.score_dog

    def add(self, text, side, points, key):
        self.testimonies.append(Testimony(text, side, float(points), key))
        if side == "fav":
            self.score_fav += points
        else:
            self.score_dog += points

    def doctrine_flags(self) -> dict[str, float]:
        """Signed (+fav / -dog) indicator per doctrine key, for the Doctrine Tribunal."""
        out: dict[str, float] = {}
        for t in self.testimonies:
            out[t.key] = out.get(t.key, 0.0) + (1.0 if t.side == "fav" else -1.0)
        return {k: float(np.sign(v)) for k, v in out.items()}

    def to_dict(self) -> dict:
        return {
            "engine": self.engine, "winner": self.winner, "net": round(self.net, 2),
            "score_fav": round(self.score_fav, 2), "score_dog": round(self.score_dog, 2),
            "goals_fav": self.goals_fav, "goals_dog": self.goals_dog,
            "confidence": self.confidence, "caveats": self.caveats, "table": self.table,
            "testimonies": [t.__dict__ for t in self.testimonies], "features": self.features,
        }


def within_before(x: float, cusp: float, orb: float) -> bool:
    """x lies 0..orb degrees *before* the cusp (lower longitude) and in the cusp's sign."""
    d = (cusp - x) % 360
    return 0 < d <= orb and ephem.sign_of(x) == ephem.sign_of(cusp)


def within_after(x: float, cusp: float, orb: float) -> bool:
    """x lies 0..orb degrees *after* the cusp (just inside the house), same sign."""
    d = (x - cusp) % 360
    return 0 <= d <= orb and ephem.sign_of(x) == ephem.sign_of(cusp)


def sep(a: float, b: float) -> float:
    return abs(float(ephem.angdiff(a, b)))
