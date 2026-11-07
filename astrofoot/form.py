"""Form check: when at least 2 of the 3 classical engines back the same team to win (favourite or underdog),
look at how that team has been scoring.

Windows, all strictly before the game:
  - its last 5 games at the same venue type (home games if it is at home, away games if it is away),
  - its last 5 games overall,
  - its last 3 meetings with this opponent (any venue),
and, for context, how the opponent has been conceding (last 5 at its venue type, last 5 overall).

From these a form estimate of the team's expected goals is made (a fixed, transparent blend: attack 55% venue /
45% overall, or 40/30/30 with three meetings; that attack averaged with the opponent's conceding, 60% venue /
40% overall), giving P(scores at least once) = 1 - e^-λ and P(2+) = 1 - e^-λ(1 + λ). The market's calibrated
P(scores) is shown beside it.

Backtest (research.py overunder → data/models/form.json): over the historical corpus, adding this form estimate
to the market does not improve the prediction of whether a team scores; the odds already contain it.

Data, deduplicated: the research corpus (data/work/matches.parquet, refreshed weekly); every result of the current
and previous season from football-data.co.uk, refreshed daily by the GitHub cycle into ledger/recent_results.csv
(the corpus lags and misses games); and every settled game in the live ledger. Club names are football-data.co.uk's
throughout.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import MODELS, ROOT, WORK

FILE = MODELS / "form.json"
RECENT = ROOT / "ledger" / "recent_results.csv"
RECENT_EVERY_HOURS = 20
ENGINES = ("rao", "chokoisky", "frawley")
N_VENUE, N_ALL, N_H2H = 5, 5, 3
XG_STEPS = (0.0, 0.8, 1.0, 1.2, 1.5, 2.0)      # expected-goals filter thresholds on the Form check tab


def load_research() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


# ----------------------------------------------------------------------------- history
def _corpus() -> pd.DataFrame:
    p = WORK / "matches.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["ko", "home", "away", "gh", "ga", "division"])
    m = pd.read_parquet(p, columns=["kickoff_utc", "home", "away", "goals_home", "goals_away", "division"])
    m = m[m.goals_home.notna() & m.goals_away.notna()]
    return pd.DataFrame({"ko": pd.to_datetime(m.kickoff_utc, utc=True), "home": m.home, "away": m.away,
                         "gh": m.goals_home.astype(int), "ga": m.goals_away.astype(int), "division": m.division})


def _recent(path: Path = RECENT) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["ko", "home", "away", "gh", "ga", "division"])
    r = pd.read_csv(path)
    return pd.DataFrame({"ko": pd.to_datetime(r.kickoff_utc, utc=True), "home": r.home, "away": r.away,
                         "gh": r.goals_home.astype(int), "ga": r.goals_away.astype(int), "division": r.division})


def refresh_recent(now, fetch_csv, leagues, path: Path = RECENT, log=print, force: bool = False) -> int:
    """Download every result of the current and previous season for `leagues` (football-data.co.uk) into
    ledger/recent_results.csv. Run by the cycle at most every RECENT_EVERY_HOURS. Returns rows written (-1 skipped)."""
    from datetime import timedelta

    from . import live
    meta = path.with_suffix(".meta.json")
    if not force and path.exists() and meta.exists():
        # the refresh time is stored in the file (a fresh git checkout resets modification times)
        try:
            done = datetime.fromisoformat(json.loads(meta.read_text())["generated_at"])
            if (now - done).total_seconds() < RECENT_EVERY_HOURS * 3600:
                return -1
        except (OSError, ValueError, KeyError):
            pass
    rows, failed = [], []
    urls = set()
    for div in leagues:
        for back in (0, 365):
            urls.add((div, live.results_url(div, now - timedelta(days=back))))
    for div, url in sorted(urls):
        try:
            df = fetch_csv(url)
        except Exception as e:  # noqa: BLE001 - a missing file (new season not started, league renamed) is fine
            failed.append(f"{url.rsplit('/', 2)[-2]}/{url.rsplit('/', 1)[-1]} ({type(e).__name__})")
            continue
        for _, r in df.iterrows():
            if live._div(r) != div:
                continue
            gh, ga = pd.to_numeric(r.get("FTHG"), errors="coerce"), pd.to_numeric(r.get("FTAG"), errors="coerce")
            if not (np.isfinite(gh) and np.isfinite(ga)):
                continue
            ko = live._kickoff_utc(r.get("Date"), r.get("Time"))
            if ko is None or ko > now or (now - ko).days > 550:
                continue
            rows.append({"kickoff_utc": ko.isoformat(), "division": div, "home": str(r.get("HomeTeam", "")).strip(),
                         "away": str(r.get("AwayTeam", "")).strip(), "goals_home": int(gh), "goals_away": int(ga)})
    if not rows:
        log(f"recent results: nothing downloaded ({len(failed)} file(s) unavailable)")
        return 0
    out = pd.DataFrame(rows).drop_duplicates(subset=["kickoff_utc", "home", "away"]).sort_values(["kickoff_utc", "home"])
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    meta.write_text(json.dumps({"generated_at": now.isoformat(timespec="seconds"), "games": len(out),
                                "unavailable": failed}, indent=1) + "\n")
    log(f"recent results: {len(out)} games from {out.division.nunique()} leagues for form checks"
        + (f"; unavailable: {', '.join(failed)}" if failed else ""))
    return len(out)


@lru_cache(maxsize=4)
def _history_cached(corpus_mtime: float, recent_mtime: float, live_sig: tuple) -> dict[str, list[tuple]]:
    """team -> [(kickoff, venue 'H'/'A', opponent, goals for, goals against, division)], newest first."""
    c = pd.concat([_recent(), _corpus()], ignore_index=True)     # recent first: it wins duplicates
    live = pd.DataFrame(list(live_sig), columns=["ko", "home", "away", "gh", "ga", "division"])
    if len(live):
        live["ko"] = pd.to_datetime(live.ko, utc=True)
    games = pd.concat([c, live], ignore_index=True)
    games["day"] = games.ko.dt.strftime("%Y-%m-%d")
    games = games.drop_duplicates(subset=["day", "home", "away"], keep="first")
    out: dict[str, list[tuple]] = {}
    for g in games.itertuples(index=False):
        out.setdefault(g.home, []).append((g.ko, "H", g.away, g.gh, g.ga, g.division))
        out.setdefault(g.away, []).append((g.ko, "A", g.home, g.ga, g.gh, g.division))
    for v in out.values():
        v.sort(key=lambda t: t[0], reverse=True)
    return out


def history(recs: list[dict]) -> dict[str, list[tuple]]:
    """Team histories from the corpus plus the settled games among `recs` (joined live/manual records)."""
    p = WORK / "matches.parquet"
    mtime = p.stat().st_mtime if p.exists() else 0.0
    rmtime = RECENT.stat().st_mtime if RECENT.exists() else 0.0
    sig = tuple(sorted((r["kickoff_utc"], r["home"], r["away"], int(r["result"]["goals_home"]),
                        int(r["result"]["goals_away"]), r["division"])
                       for r in recs if r.get("result") and r["result"].get("goals_home") is not None))
    return _history_cached(mtime, rmtime, sig)


# ----------------------------------------------------------------------------- analysis
def backed_side(rec: dict) -> tuple[str | None, int, dict]:
    """The side ('home'/'away') that at least 2 of the 3 classical engines call to win, with the count."""
    side_of = {"fav": "home" if rec["fav_is_home"] else "away", "dog": "away" if rec["fav_is_home"] else "home"}
    calls = {e: side_of.get((rec["predictions"].get(e) or {}).get("winner")) for e in ENGINES}
    for side in ("home", "away"):
        n = sum(1 for c in calls.values() if c == side)
        if n >= 2:
            return side, n, calls
    return None, max(sum(1 for c in calls.values() if c == s) for s in ("home", "away")), calls


def _window(games: list[tuple]) -> dict:
    rows = [{"date": g[0].strftime("%Y-%m-%d"), "venue": g[1], "opponent": g[2], "gf": int(g[3]), "ga": int(g[4]),
             "res": "W" if g[3] > g[4] else "L" if g[3] < g[4] else "D", "division": g[5]} for g in games]
    n = len(rows)
    if not n:
        return {"n": 0, "games": []}
    gf = [r["gf"] for r in rows]
    ga = [r["ga"] for r in rows]
    return {"n": n, "games": rows, "gf": sum(gf) / n, "ga": sum(ga) / n,
            "scored": sum(1 for x in gf if x > 0), "scored2": sum(1 for x in gf if x >= 2),
            "conceded_any": sum(1 for x in ga if x > 0), "clean_sheets": sum(1 for x in ga if x == 0),
            "w": sum(r["res"] == "W" for r in rows), "d": sum(r["res"] == "D" for r in rows),
            "l": sum(r["res"] == "L" for r in rows)}


def form_lambda(att_venue, att_all, att_h2h, def_venue, def_all) -> float | None:
    """The fixed blend described in the module docstring (None without enough history)."""
    if att_venue is None or att_all is None:
        return None
    att = 0.4 * att_venue + 0.3 * att_all + 0.3 * att_h2h if att_h2h is not None else 0.55 * att_venue + 0.45 * att_all
    if def_venue is None or def_all is None:
        lam = att
    else:
        lam = 0.5 * att + 0.5 * (0.6 * def_venue + 0.4 * def_all)
    return float(min(max(lam, 0.05), 5.0))


def side_counts(rec: dict) -> dict[str, int]:
    """How many of the 3 classical engines call each side to win: {'home': n, 'away': n}."""
    _, _, calls = backed_side(rec)
    return {s: sum(1 for c in calls.values() if c == s) for s in ("home", "away")}


def analyse(rec: dict, hist: dict[str, list[tuple]], side: str | None = None) -> dict:
    """Form check for one game. By default the team backed by 2+ engines (`qualifies` is False if none);
    with `side` ('home'/'away'), that team whatever its engine support (`agree` = engines calling it to win)."""
    from . import teamgoals
    backed, n_back, calls = backed_side(rec)
    if side is not None:
        n_back = sum(1 for c in calls.values() if c == side)
    else:
        side = backed
    out = {"qualifies": side is not None, "agree": n_back, "calls": calls}
    if side is None:
        return out
    team, opp = (rec["home"], rec["away"]) if side == "home" else (rec["away"], rec["home"])
    venue = "H" if side == "home" else "A"
    ko = pd.Timestamp(rec["kickoff_utc"]).tz_convert("UTC")
    past = [g for g in hist.get(team, []) if g[0] < ko]
    opp_past = [g for g in hist.get(opp, []) if g[0] < ko]
    w_venue = _window([g for g in past if g[1] == venue][:N_VENUE])
    w_all = _window(past[:N_ALL])
    w_h2h = _window([g for g in past if g[2] == opp][:N_H2H])
    o_venue = _window([g for g in opp_past if g[1] != venue][:N_VENUE])
    o_all = _window(opp_past[:N_ALL])
    lam = form_lambda(w_venue.get("gf") if w_venue["n"] >= 3 else None, w_all.get("gf") if w_all["n"] >= 3 else None,
                      w_h2h.get("gf") if w_h2h["n"] >= N_H2H else None,
                      o_venue.get("ga") if o_venue["n"] >= 3 else None, o_all.get("ga") if o_all["n"] >= 3 else None)
    mk = rec["predictions"]["market"]
    p_home, p_away = (mk["fav"], mk["dog"]) if rec["fav_is_home"] else (mk["dog"], mk["fav"])
    ph, pa = teamgoals.score_probs(p_home, p_away)
    lh, la = teamgoals.rates(p_home, p_away)
    lam_mkt = float((lh if side == "home" else la)[0])
    res = rec.get("result")
    scored = None
    if res and res.get("goals_home") is not None:
        scored = int(res["goals_home"] if side == "home" else res["goals_away"])
    is_fav = (side == "home") == bool(rec["fav_is_home"])
    out.update({
        "side": side, "team": team, "opponent": opp, "role": "favourite" if is_fav else "underdog",
        "venue_word": "home" if venue == "H" else "away",
        "team_venue": w_venue, "team_all": w_all, "h2h": w_h2h, "opp_venue": o_venue, "opp_all": o_all,
        "lam_form": lam, "p_form": None if lam is None else 1 - math.exp(-lam),
        "p_form2": None if lam is None else 1 - math.exp(-lam) * (1 + lam),
        "p_market": ph if side == "home" else pa, "lam_market": lam_mkt,
        "p_market2": 1 - math.exp(-lam_mkt) * (1 + lam_mkt),
        "goals": scored, "scored_hit": None if scored is None else scored > 0,
    })
    return out


# ----------------------------------------------------------------------------- research
def backtest(matches: pd.DataFrame, engines: pd.DataFrame) -> dict:
    """Walk-forward: does the form estimate add to the market's P(team scores)? Overall and for teams backed by
    2+ engines."""
    from sklearn.linear_model import LogisticRegression

    from . import teamgoals
    m = pd.concat([matches.reset_index(drop=True), engines[["rao_win", "chok_win", "fraw_win"]].reset_index(drop=True)], axis=1)
    m = m[m.goals_home.notna() & m.p_home.notna()].sort_values("kickoff_utc").reset_index(drop=True)
    m["mid"] = np.arange(len(m))
    side = lambda v, t, o, gf, ga: pd.DataFrame({"mid": m.mid, "ko": m.kickoff_utc, "team": t, "opp": o,  # noqa: E731
                                                  "venue": v, "gf": gf, "ga": ga})
    L = pd.concat([side("H", m.home, m.away, m.goals_home, m.goals_away),
                   side("A", m.away, m.home, m.goals_away, m.goals_home)]).sort_values(["ko", "mid"]).reset_index(drop=True)

    def prior_mean(keys, col, n):
        return L.groupby(keys, sort=False)[col].transform(lambda s: s.shift(1).rolling(n, min_periods=n).mean())
    L["gf5"], L["ga5"] = prior_mean(["team"], "gf", 5), prior_mean(["team"], "ga", 5)
    L["gf5v"], L["ga5v"] = prior_mean(["team", "venue"], "gf", 5), prior_mean(["team", "venue"], "ga", 5)
    L["pair"] = L.team + "|" + L.opp
    L["gf_h2h"] = prior_mean(["pair"], "gf", 3)
    opp = L[["mid", "team", "ga5v", "ga5"]].rename(columns={"team": "opp", "ga5v": "o_ga5v", "ga5": "o_ga5"})
    L = L.merge(opp, on=["mid", "opp"])
    lh, la = teamgoals.rates(m.p_home.to_numpy(), m.p_away.to_numpy())
    mk = pd.DataFrame({"mid": m.mid, "season": m.season, "lh": lh, "la": la, "fav_is_home": m.fav_is_home,
                       "p_home": m.p_home, "p_away": m.p_away, "rao": m.rao_win, "chok": m.chok_win, "fraw": m.fraw_win})
    L = L.merge(mk, on="mid").dropna(subset=["gf5", "gf5v", "o_ga5v", "o_ga5"])
    att = np.where(L.gf_h2h.notna(), 0.4 * L.gf5v + 0.3 * L.gf5 + 0.3 * L.gf_h2h.fillna(0), 0.55 * L.gf5v + 0.45 * L.gf5)
    L["lam_form"] = np.clip(0.5 * att + 0.5 * (0.6 * L.o_ga5v + 0.4 * L.o_ga5), 0.05, 5)
    raw = 1 - np.exp(-np.where(L.venue == "H", L.lh, L.la))
    L["p_mkt"] = raw
    L["p_form"] = 1 - np.exp(-L.lam_form)
    L["y"] = (L.gf > 0).astype(float)
    is_fav = np.where(L.venue == "H", L.fav_is_home.astype(bool), ~L.fav_is_home.astype(bool))
    code = np.where(is_fav, 1, -1)
    L["agree"] = sum((L[c] == code).astype(int) for c in ("rao", "chok", "fraw"))
    lg = lambda p: np.log(np.clip(p, 0.01, 0.99) / (1 - np.clip(p, 0.01, 0.99)))  # noqa: E731
    seasons = sorted(L.season.unique())
    out = {"windows": {"venue": N_VENUE, "overall": N_ALL, "h2h": N_H2H}}
    # the factor that does sort them: the team's expected goals implied by the odds (backed teams)
    lam_mkt = np.where(L.venue == "H", L.lh, L.la)
    backed = (L.agree >= 2).to_numpy()
    out["by_xg"] = [{"min": t, "n": int((backed & (lam_mkt >= t)).sum()),
                     "scored": float(L.y.to_numpy()[backed & (lam_mkt >= t)].mean())} for t in XG_STEPS]
    # the same for each exact number of engines calling the team to win (0, 1, 2, 3 of 3)
    agree, yv = L.agree.to_numpy(), L.y.to_numpy()
    out["by_agree"] = {str(k): [{"min": t, "n": int(((agree == k) & (lam_mkt >= t)).sum()),
                                 "scored": float(yv[(agree == k) & (lam_mkt >= t)].mean())
                                 if ((agree == k) & (lam_mkt >= t)).any() else None} for t in XG_STEPS]
                       for k in range(4)}
    for name, sub in (("all", L), ("backed", L[L.agree >= 2])):
        y = sub.y.to_numpy()
        res = {}
        for feats in (("p_mkt",), ("p_form",), ("p_mkt", "p_form")):
            X = np.c_[tuple(lg(sub[f].to_numpy()) for f in feats)]
            pc = np.full(len(sub), np.nan)
            for s in seasons[3:]:
                tr, te = (sub.season < s).to_numpy(), (sub.season == s).to_numpy()
                if tr.sum() >= 1000 and te.any():
                    pc[te] = LogisticRegression(C=1e6, max_iter=500).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
            ok = ~np.isnan(pc)
            res["+".join(f[2:] for f in feats)] = float(-(y[ok] * np.log(pc[ok]) + (1 - y[ok]) * np.log(1 - pc[ok])).mean())
        both = LogisticRegression(C=1e6, max_iter=500).fit(np.c_[lg(sub.p_mkt.to_numpy()), lg(sub.p_form.to_numpy())], y)
        q = pd.qcut(sub.p_form - sub.p_mkt, 5, labels=False)
        tab = sub.assign(q=q).groupby("q").agg(n=("y", "size"), scored=("y", "mean"), form=("p_form", "mean"))
        out[name] = {"n": int(len(sub)), "scored_rate": float(sub.y.mean()), "log_loss": res,
                     "coef_market": float(both.coef_[0, 0]), "coef_form": float(both.coef_[0, 1]),
                     "by_form_vs_market": [{"quintile": int(i) + 1, "n": int(r.n), "scored": float(r.scored),
                                            "form": float(r.form)} for i, r in tab.iterrows()]}
    return out


def write(result: dict):
    FILE.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
