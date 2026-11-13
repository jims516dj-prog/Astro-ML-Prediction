"""Does the date-only astrology / numerology of a club's founding date tell whether the day favours it, or whether
it scores, beyond the bookmaker odds? Writes data/models/teamday.json (shown on the soccer pages).

The games: the match history (data/work/matches.parquet) plus the settled games of the live record, men's and women's,
that the history does not have (odds from the sealed forecast, the final score from its result). The founding dates:
the founding table, and the dates you entered in the app (data/app.sqlite3) when this runs on your computer.

  --mine   write data/models/teamday_mine.json instead (your computer's result, with your dates; git-ignored), which
           the soccer pages then show in place of the shared one."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from astrofoot import geo, teamday, teamgoals  # noqa: E402
from astrofoot.tennis import daychart as dc  # noqa: E402

EPS = 1e-6


def ll(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def season_of(ts) -> str:
    t = pd.Timestamp(ts)
    y = t.year if t.month >= 7 else t.year - 1
    return f"{y}/{str(y + 1)[-2:]}"


def live_games(history: pd.DataFrame) -> pd.DataFrame:
    """Settled live-record games (men's and women's) the history does not have, as history rows."""
    from astrofoot import live
    seen = {(h, a, str(k)[:10]) for h, a, k in zip(history.home, history.away, history.kickoff_utc)}
    rows = []
    for ledger, women in ((live.LEDGER, False), (live.LEDGER / "women", True)):
        try:
            recs = live.records(ledger)
        except Exception as e:  # noqa: BLE001
            print("live record unavailable:", ledger, e)
            continue
        for r in recs:
            res, o = r.get("result") or {}, r.get("odds") or {}
            if r.get("status") != "settled" or res.get("goals_home") is None or not all(o.get(k) for k in ("home", "draw", "away")):
                continue
            if (r["home"], r["away"], str(r["kickoff_utc"])[:10]) in seen:
                continue
            inv = {k: 1 / float(o[k]) for k in ("home", "draw", "away")}
            tot = sum(inv.values())                    # the bookmaker's margin taken out, as for the history
            rows.append({"season": season_of(r["kickoff_utc"]), "kickoff_utc": pd.Timestamp(r["kickoff_utc"]),
                         "home": r["home"], "away": r["away"], "lat": r.get("venue_lat"), "lon": r.get("venue_lon"),
                         "p_home": inv["home"] / tot, "p_away": inv["away"] / tot,
                         "goals_home": int(res["goals_home"]), "goals_away": int(res["goals_away"]), "women": women})
    return pd.DataFrame(rows)


def main():
    m = pd.read_parquet("data/work/matches.parquet")
    m = m.dropna(subset=["p_home", "p_away", "goals_home", "goals_away"]).reset_index(drop=True)
    m["women"] = False
    extra = live_games(m)
    print(f"{len(m):,} history games, {len(extra):,} settled live-record games not in the history")
    if len(extra):
        m = pd.concat([m, extra], ignore_index=True)
    yours = teamday.user_dates()
    print(f"{len(yours)} founding dates you entered in the app")
    tz_of = {}
    rows = []
    for r in m.itertuples():
        key = (round(float(r.lat), 3), round(float(r.lon), 3)) if pd.notna(r.lat) and pd.notna(r.lon) else None
        if key not in tz_of:
            tz_of[key] = geo.timezone_at(*key) if key else None
        w = bool(r.women)
        f_h, f_a = teamday.founding(r.home, resolve=False, women=w), teamday.founding(r.away, resolve=False, women=w)
        if not f_h and not f_a:
            continue
        rd = teamday.reading(r.home, r.away, r.kickoff_utc, r.lat, r.lon, resolve=False, women=w)
        ph, pa = teamgoals.score_probs(float(r.p_home), float(r.p_away))
        for side, f, p_score, p_win, scored, won, opp in (
                ("home", f_h, ph, r.p_home, r.goals_home > 0, r.goals_home > r.goals_away, "away"),
                ("away", f_a, pa, r.p_away, r.goals_away > 0, r.goals_away > r.goals_home, "home")):
            if not f:
                continue
            x = rd[side]
            fav = rd["favours"]
            mine = 1 if side == "home" else 2
            rows.append({"season": r.season, "date": r.kickoff_utc, "team": x["team"], "side": side,
                         "yours": f.get("source") == "you", "live": pd.isna(getattr(r, "match_id", None)),
                         "p_score": p_score, "p_win": float(p_win), "scored": int(scored), "won": int(won),
                         "astro": x["astro"]["score"], "attack": x["attack"]["score"], "num": x["num"]["score"],
                         "num_attack": x["num_attack"]["score"], "score_astro": x["score_astro"], "score_num": x["score_num"],
                         "day_astro": 0 if fav["astro"] == 0 else (1 if fav["astro"] == mine else -1),
                         "day_num": 0 if fav["num"] == 0 else (1 if fav["num"] == mine else -1),
                         "contacts": dc.contact_vector(f["date"], rd["day"], rd["tz"]),
                         "numvec": dc.num_vector(f["date"], f["name"], rd["day"])})
    d = pd.DataFrame(rows)
    print(f"{len(d):,} team-matches with a founding date known to the day")

    def group(mask, y, p):
        n = int(mask.sum())
        if not n:
            return {"n": 0}
        yy, pp = d.loc[mask, y].to_numpy(), d.loc[mask, p].to_numpy()
        se = float(np.sqrt((pp * (1 - pp)).sum()) / n)
        return {"n": n, "rate": float(yy.mean()), "expected": float(pp.mean()), "diff": float(yy.mean() - pp.mean()), "se": se}

    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n": int(len(d)),
           "teams": int(d.team.nunique()), "seasons": sorted(map(str, d.season.unique())),
           "live_games": int(d.live.sum()), "your_teams": int(d[d.yours].team.nunique()),
           "your_team_matches": int(d.yours.sum()), "includes_your_dates": bool(yours)}
    print(f"  your dates: {out['your_teams']} teams, {out['your_team_matches']} team-matches")
    out["scoring"] = {k: {str(v): group(d[k] == v, "scored", "p_score") for v in (1, 0, -1)} for k in ("score_astro", "score_num")}
    both = (d.score_astro == 1) & (d.score_num == 1)
    out["scoring"]["both"] = {"1": group(both, "scored", "p_score")}
    out["day"] = {k: {str(v): group(d[k] == v, "won", "p_win") for v in (1, 0, -1)} for k in ("day_astro", "day_num")}

    # machine learning: the team's own contacts and numbers, on top of the odds' scoring chance
    seasons = sorted(d.season.unique())
    test_seasons = seasons[-2:]
    tr, te = d[~d.season.isin(test_seasons)], d[d.season.isin(test_seasons)]

    def X(df, extra):
        base = logit(df.p_score.to_numpy())[:, None]
        if extra == "none":
            return base
        parts = [base]
        if extra in ("astro", "both"):
            parts += [np.nan_to_num(np.vstack(df.contacts.to_numpy())), df[["attack", "astro"]].fillna(0).to_numpy()]
        if extra in ("num", "both"):
            parts += [np.nan_to_num(np.vstack(df.numvec.to_numpy())), df[["num_attack", "num"]].fillna(0).to_numpy()]
        return np.hstack(parts)

    ml = {}
    base_ll = None
    for extra in ("none", "astro", "num", "both"):
        best = None
        for C in (0.01, 0.1, 1.0):
            lr = LogisticRegression(C=C, max_iter=3000).fit(X(tr, extra), tr.scored)
            p = lr.predict_proba(X(te, extra))[:, 1]
            l = ll(te.scored.to_numpy(), p)
            if best is None or l.mean() < best[0].mean():
                best = (l, C, p)
        l, C, p = best
        if extra == "none":
            base_ll = l
        dlt = l - base_ll
        ml[extra] = {"C": C, "log_loss": float(l.mean()), "accuracy": float(((p > 0.5) == te.scored.to_numpy()).mean()),
                     "delta": float(dlt.mean()), "se": float(dlt.std(ddof=1) / np.sqrt(len(dlt)))}
        print(f"  {extra:6s} C={C}: log loss {l.mean():.4f}  Δ {dlt.mean():+.5f} ± {dlt.std(ddof=1) / np.sqrt(len(dlt)):.5f}")
    out["ml"] = {"train_seasons": [str(s) for s in seasons if s not in test_seasons], "test_seasons": [str(s) for s in test_seasons],
                 "n_test": int(len(te)), "market_only": float(ll(te.scored.to_numpy(), te.p_score.to_numpy()).mean()), **ml}
    dest = teamday.RESEARCH_MINE if "--mine" in sys.argv else teamday.RESEARCH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, default=float))
    print("written:", dest)
    for k, g in out["scoring"].items():
        print("scoring", k, {v: (x.get("n"), round(x.get("rate", 0), 4), round(x.get("expected", 0), 4)) for v, x in g.items()})
    for k, g in out["day"].items():
        print("day", k, {v: (x.get("n"), round(x.get("rate", 0), 4), round(x.get("expected", 0), 4)) for v, x in g.items()})


if __name__ == "__main__":
    main()
