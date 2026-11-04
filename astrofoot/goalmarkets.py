"""The three goal predictions for any match: over/under 2.5, home or away goal, both teams to score.

One function used everywhere (Analyze, Dataset, Live record, Top picks), so a game gets the same numbers
wherever it is shown. All three come from the market: over/under from its over/under price (overunder.py),
the other two from the 1X2 odds via Poisson scoring rates (teamgoals.py), each recalibrated walk-forward on
the historical corpus. The classical engines' predicted scores are shown alongside as "astrology agrees".
"""
from __future__ import annotations

from . import doublechance, overunder, teamgoals

ENGINES = ("rao", "chokoisky", "frawley")


def p_over_from_odds(over: float | None, under: float | None) -> float | None:
    """Proportionally de-vigged P(over 2.5), the same way the training data was built."""
    try:
        o, u = float(over), float(under)
    except (TypeError, ValueError):
        return None
    if o <= 1 or u <= 1:
        return None
    return (1 / o) / (1 / o + 1 / u)


def markets(p_home: float, p_away: float, p_over25: float | None = None,
            engine_scores: dict | None = None, result: tuple[int, int] | None = None,
            home: str = "Home", away: str = "Away", ou_cal: dict | None = None, ts_cal: dict | None = None,
            p_draw: float | None = None, engine_calls: dict | None = None) -> dict:
    """p_home/p_away: de-vigged 1X2 win probabilities. p_over25: de-vigged over-2.5 price, if any.
    engine_scores: {engine: (home goals, away goals)} predicted by each classical engine.
    result: final score (home, away), if known."""
    scores = {e: (engine_scores or {}).get(e) for e in ENGINES}
    known = [s for s in scores.values() if s is not None]
    gh, ga = result if result else (None, None)

    p_ov = overunder.calibrate(p_over25, ou_cal)
    if p_ov is None:
        ou = None
    else:
        over = p_ov > 0.5
        ou = {"p_over": p_ov, "pick": "over" if over else "under", "pick_p": max(p_ov, 1 - p_ov),
              "agree": sum(1 for s in known if (sum(s) > 2.5) == over),
              "hit": None if gh is None else ((gh + ga > 2.5) == over)}

    ph, pa = teamgoals.score_probs(p_home, p_away, ts_cal)
    side = "home" if ph >= pa else "away"
    j = 0 if side == "home" else 1
    ts = {"p_home": ph, "p_away": pa, "pick": side, "pick_p": max(ph, pa), "team": home if side == "home" else away,
          "agree": sum(1 for s in known if s[j] > 0),
          "hit": None if gh is None else ((gh if side == "home" else ga) > 0)}

    pb = teamgoals.btts_prob(p_home, p_away, ts_cal)
    yes = pb > 0.5
    bt = {"p_yes": pb, "pick": "yes" if yes else "no", "pick_p": max(pb, 1 - pb),
          "agree": sum(1 for s in known if (min(s) > 0) == yes),
          "hit": None if gh is None else ((gh > 0 and ga > 0) == yes)}
    p15 = teamgoals.over15_prob(p_home, p_away, ts_cal)
    o15 = p15 > 0.5
    o = {"p_over": p15, "pick": "over" if o15 else "under", "pick_p": max(p15, 1 - p15),
         "agree": sum(1 for s in known if (sum(s) > 1.5) == o15),
         "hit": None if gh is None else ((gh + ga > 1.5) == o15)}

    pd_ = p_draw if p_draw is not None else max(0.0, 1 - p_home - p_away)
    pr = doublechance.probs(p_home, pd_, p_away)
    pick = max(doublechance.OPTIONS, key=pr.get)
    calls = engine_calls or {e: (None if s is None else doublechance.outcome(*s)) for e, s in scores.items()}
    cover = doublechance.COVERS[pick]
    dc = {"probs": pr, "pick": pick, "label": doublechance.LABEL[pick], "pick_p": pr[pick],
          "agree": sum(1 for c in calls.values() if c in cover), "n": sum(1 for c in calls.values() if c),
          "hit": None if gh is None else (doublechance.outcome(gh, ga) in cover)}
    return {"ou": ou, "ts": ts, "bt": bt, "o15": o, "dc": dc, "engine_scores": scores, "n_engines": len(known)}


def from_analysis(a: dict, result: tuple[int, int] | None = None) -> dict:
    """Goal markets for a service.analyse() result (Analyze page and saved matches).

    Team A is treated as "home" unless Team B was marked as the home side."""
    inp = a.get("inputs", {})
    b_home = inp.get("home_side") == "B"
    mk = a["market"]
    p_a, p_b = (mk["p_fav"], mk["p_dog"]) if a["fav_is_a"] else (mk["p_dog"], mk["p_fav"])
    home, away = (inp.get("team_b"), inp.get("team_a")) if b_home else (inp.get("team_a"), inp.get("team_b"))
    p_home, p_away = (p_b, p_a) if b_home else (p_a, p_b)
    scores = {}
    for e in ENGINES:
        v = a["verdicts"].get(e) or {}
        if v.get("goals_fav") is None or v.get("goals_dog") is None:
            continue
        g_a, g_b = (v["goals_fav"], v["goals_dog"]) if a["fav_is_a"] else (v["goals_dog"], v["goals_fav"])
        scores[e] = (g_b, g_a) if b_home else (g_a, g_b)
    if result is not None and b_home:
        result = (result[1], result[0])          # result is given as (Team A, Team B)
    side = {"fav": "a", "dog": "b"} if a["fav_is_a"] else {"fav": "b", "dog": "a"}
    calls = {}
    for e in ENGINES:
        w = (a["verdicts"].get(e) or {}).get("winner")
        if w == "draw":
            calls[e] = "draw"
        elif w in side:
            calls[e] = "home" if (side[w] == "b") == b_home else "away"
    return markets(p_home, p_away, inp.get("p_over25"), scores, result, home or "Home", away or "Away",
                   p_draw=mk.get("p_draw"), engine_calls=calls)
