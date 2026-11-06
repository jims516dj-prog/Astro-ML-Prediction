"""My picks: the user's own selection of games and outcomes for a day, scored once the games are played.

Every outcome a game can be picked on comes with the same calibrated probability the other pages show
(the market's, recalibrated per market; see overunder.py, teamgoals.py, doublechance.py). A pick made after
kickoff is flagged and left out of the score.
"""
from __future__ import annotations

MARKET_NAMES = {"result": "Match result", "dc": "Double chance", "o15": "Over/under 1.5", "o25": "Over/under 2.5",
                "hs": "Home team to score", "as": "Away team to score", "btts": "Both teams to score"}


def options(r: dict) -> list[dict]:
    """Every pickable outcome of one game (a joined live/manual record), most probable first."""
    home, away = r["home"], r["away"]
    probs = r["predictions"].get("synthesis") or r["predictions"]["market"]
    fh = r["fav_is_home"]
    p_home, p_away = (probs["fav"], probs["dog"]) if fh else (probs["dog"], probs["fav"])
    out = [("result:home", f"{home} win", p_home), ("result:draw", "Draw", probs["draw"]),
           ("result:away", f"{away} win", p_away)]
    dc = r.get("dc_probs") or {}
    if dc:
        out += [("dc:1X", f"{home} or draw (1X)", dc["1X"]), ("dc:X2", f"{away} or draw (X2)", dc["X2"]),
                ("dc:12", "No draw (12)", dc["12"])]
    if r.get("o15_p_over") is not None:
        out += [("o15:over", "Over 1.5 goals", r["o15_p_over"]), ("o15:under", "Under 1.5 goals", 1 - r["o15_p_over"])]
    if r.get("ou_p_over") is not None:
        out += [("o25:over", "Over 2.5 goals", r["ou_p_over"]), ("o25:under", "Under 2.5 goals", 1 - r["ou_p_over"])]
    if r.get("ts_p_home") is not None:
        out += [("hs:yes", f"{home} to score", r["ts_p_home"]), ("hs:no", f"{home} not to score", 1 - r["ts_p_home"]),
                ("as:yes", f"{away} to score", r["ts_p_away"]), ("as:no", f"{away} not to score", 1 - r["ts_p_away"])]
    if r.get("bt_p_yes") is not None:
        out += [("btts:yes", "Both teams to score", r["bt_p_yes"]),
                ("btts:no", "Not both teams to score", 1 - r["bt_p_yes"])]
    opts = [{"code": c, "market": MARKET_NAMES[c.split(":")[0]], "label": lab, "p": float(p)} for c, lab, p in out]
    return sorted(opts, key=lambda o: -o["p"])


def won(code: str, gh: int, ga: int) -> bool:
    """Did the outcome `code` happen with this 90-minute score (home goals, away goals)?"""
    market, sel = code.split(":")
    res = "home" if gh > ga else "away" if gh < ga else "draw"
    return {
        "result": lambda: res == sel,
        "dc": lambda: res in {"1X": ("home", "draw"), "X2": ("away", "draw"), "12": ("home", "away")}[sel],
        "o15": lambda: (gh + ga > 1.5) == (sel == "over"),
        "o25": lambda: (gh + ga > 2.5) == (sel == "over"),
        "hs": lambda: (gh > 0) == (sel == "yes"),
        "as": lambda: (ga > 0) == (sel == "yes"),
        "btts": lambda: (gh > 0 and ga > 0) == (sel == "yes"),
    }[market]()


def agree(code: str, engine_scores: dict) -> tuple[int, int]:
    """How many classical engines' predicted scores agree with the outcome `code`: (agreeing, engines with a
    score). For a match-result pick this is the Live record's agreement count."""
    known = [s for s in (engine_scores or {}).values() if s is not None]
    return sum(1 for s in known if won(code, s[0], s[1])), len(known)


def score(picks: list[dict]) -> dict:
    """Settled, before-kickoff picks: hits vs the hit rate their probabilities implied."""
    s = [p for p in picks if p.get("hit") is not None and not p.get("late") and p.get("p") is not None]
    if not s:
        return {"n": 0}
    hits = sum(p["hit"] for p in s)
    exp = sum(p["p"] for p in s)
    var = sum(p["p"] * (1 - p["p"]) for p in s)
    return {"n": len(s), "hits": hits, "hit_rate": hits / len(s), "expected": exp / len(s), "se": var ** 0.5 / len(s)}


def all_win(picks: list[dict]) -> float | None:
    """Chance every pick comes in, treating games as independent (an estimate: a few may be related)."""
    ps = [p["p"] for p in picks if p.get("p") is not None]
    if not ps:
        return None
    out = 1.0
    for p in ps:
        out *= p
    return out
