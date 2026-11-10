"""Tennis My picks: the outcomes a tennis forecast can be picked on, with their expected probabilities,
whether the day's astrology and numerology favour the pick, and how a pick is settled."""
from __future__ import annotations

MARKETS = {"m": "Match", "f": "First set", "o": "At least one set"}


def options(r: dict, by_probability: bool = True) -> list[dict]:
    """Every pickable outcome of a joined tennis record (tennis.live.join)."""
    e, a, b = r["e"], r["p1"], r["p2"]
    out = [("m:1", f"{a} to win the match", e["a_match"]), ("m:2", f"{b} to win the match", e["b_match"]),
           ("f:1", f"{a} to win the first set", e["a_first"]), ("f:2", f"{b} to win the first set", e["b_first"]),
           ("o:1", f"{a} to win at least one set", e["a_one_set"]), ("o:2", f"{b} to win at least one set", e["b_one_set"])]
    opts = [{"code": c, "market": MARKETS[c[0]], "label": lab, "p": float(p)} for c, lab, p in out]
    return sorted(opts, key=lambda o: -o["p"]) if by_probability else opts


def side(code: str) -> int:
    return int(code.split(":")[1])


def won(code: str, set_winners: str, winner: int | None) -> bool | None:
    if not set_winners:
        return None
    m, s = code.split(":")
    return {"m": lambda: winner == int(s), "f": lambda: set_winners[0] == s, "o": lambda: s in set_winners}[m]()


def favours(code: str, day: dict) -> dict:
    """Do the day's astrology and numerology favour the player this pick backs?"""
    sd = side(code)
    a, n = day["astro"]["favours"], day["num"]["favours"]
    return {"astro": a == sd, "astro_other": a not in (0, sd), "num": n == sd, "num_other": n not in (0, sd),
            "count": int(a == sd) + int(n == sd)}
