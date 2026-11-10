"""Machine learning for tennis sets. Four models (gradient-boosted trees), each fed the same pre-match
features: A wins a given set, A wins the first set, A wins at least one set, A wins the match.

Fine-tuning, every retrain:
  1. Feature groups: statistics alone, + astrology, + numerology, + both, compared on the most recent
     12 months held out. Astrology or numerology is kept only if it lowers the held-out log loss by more
     than one standard error (paired, per match); otherwise the model ships without it and the report says so.
  2. Hyperparameters: a small grid on the chosen features, same held-out year.
  3. Walk-forward check: for each of the last seasons, train on everything before it and test on it,
     next to an Elo-only baseline.
  4. Final models are refit on all data. Each training run is a new version; the report keeps all metrics."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from . import DATA, MODELS
from .features import GROUPS, flip

BUNDLE = MODELS / "tennis.joblib"
REPORT = MODELS / "tennis.json"
HEADS = ("set", "first", "one_set", "match")
HEAD_NAMES = {"set": "Wins a given set", "first": "Wins the first set", "one_set": "Wins at least one set",
              "match": "Wins the match"}
GRID = [{"learning_rate": 0.05, "max_leaf_nodes": 15, "max_iter": 300, "l2_regularization": 1.0},
        {"learning_rate": 0.05, "max_leaf_nodes": 31, "max_iter": 400, "l2_regularization": 1.0},
        {"learning_rate": 0.1, "max_leaf_nodes": 15, "max_iter": 200, "l2_regularization": 0.0},
        {"learning_rate": 0.03, "max_leaf_nodes": 31, "max_iter": 700, "l2_regularization": 3.0}]
EPS = 1e-6


def feature_set(groups) -> list[str]:
    return [c for g in groups for c in GROUPS[g]]


def labelled(df: pd.DataFrame, head: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Rows, labels and match ids for one head; 'set' has one row per set played."""
    if head == "set":
        rep = df.loc[df.index.repeat(df.set_winners.str.len())].copy()
        rep["_k"] = rep.groupby(level=0).cumcount()
        y = np.array([s[k] == "1" for s, k in zip(rep.set_winners, rep._k)], dtype=int)
        return rep, y, rep["id"].to_numpy()
    if head == "first":
        y = (df.set_winners.str[0] == "1").astype(int).to_numpy()
    elif head == "one_set":
        y = df.set_winners.str.contains("1").astype(int).to_numpy()
    else:
        y = (df.winner == 1).astype(int).to_numpy()
    return df, y, df["id"].to_numpy()


def augmented(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, flip(df)], ignore_index=True)


def fit(df: pd.DataFrame, head: str, cols: list[str], params: dict | None = None):
    rows, y, _ = labelled(augmented(df), head)
    m = HistGradientBoostingClassifier(random_state=0, **(params or GRID[0]))
    m.fit(rows[cols].to_numpy(dtype=float), y)
    return m


def predict_p(model, df: pd.DataFrame, cols: list[str], head: str) -> np.ndarray:
    """P(A …) for each row. Set/first/match are symmetrised (A's view and 1 − B's view averaged)."""
    pa = model.predict_proba(df[cols].to_numpy(dtype=float))[:, 1]
    if head == "one_set":
        return pa
    pb = model.predict_proba(flip(df)[cols].to_numpy(dtype=float))[:, 1]
    return (pa + 1 - pb) / 2


def _ll(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def score(df_test: pd.DataFrame, head: str, p_match_level: np.ndarray) -> dict:
    rows, y, ids = labelled(df_test, head)
    # set rows repeat their match's row label; test frames are 0..n-1 indexed
    p = p_match_level[rows.index.to_numpy()] if head == "set" else p_match_level
    ll = _ll(y, p)
    return {"n": int(len(y)), "log_loss": float(ll.mean()), "brier": float(((p - y) ** 2).mean()),
            "accuracy": float(((p > 0.5) == y).mean()), "base_rate": float(y.mean()), "_ll": ll, "_ids": ids}


def per_match(s: dict) -> pd.Series:
    return pd.Series(s["_ll"]).groupby(s["_ids"]).mean()


def elo_baseline(train: pd.DataFrame, test: pd.DataFrame, head: str) -> np.ndarray:
    rows, y, _ = labelled(augmented(train), head)
    lr = LogisticRegression().fit(rows[["blend_diff"]].to_numpy() / 400, y)
    pa = lr.predict_proba(test[["blend_diff"]].to_numpy() / 400)[:, 1]
    if head == "one_set":
        return pa
    pb = lr.predict_proba(-test[["blend_diff"]].to_numpy() / 400)[:, 1]
    return (pa + 1 - pb) / 2


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _sig(x):
    return 1 / (1 + np.exp(-np.asarray(x, dtype=float)))


ASTRO_COLS = [c for c in GROUPS["astro"] if c.startswith("d_")]
NUM_COLS = [c for c in GROUPS["numerology"] if c.startswith("d_")]


def fit_side(df: pd.DataFrame, cols: list[str], kind: str, C: float = 0.03):
    """A model of set wins from astrology (or numerology) alone. 'logistic' has no intercept on A − B
    differences, so it is symmetric by construction; 'trees' is trained on both orientations."""
    rows, y, _ = labelled(df if kind == "logistic" else augmented(df), "set")
    X = rows[cols].fillna(0).to_numpy(dtype=float)
    if kind == "logistic":
        return LogisticRegression(C=C, fit_intercept=False, max_iter=2000).fit(X, y)
    return HistGradientBoostingClassifier(random_state=0, learning_rate=0.05, max_leaf_nodes=15, max_iter=200,
                                          l2_regularization=3.0).fit(X, y)


def side_logit(m, df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Learned log-odds edge for A (symmetrised)."""
    X = df[cols].fillna(0).to_numpy(dtype=float)
    if isinstance(m, LogisticRegression):
        return X @ m.coef_[0]
    pa = m.predict_proba(X)[:, 1]
    pb = m.predict_proba(-X)[:, 1]
    return (_logit(pa) - _logit(pb)) / 2


def _set_level(df: pd.DataFrame, x: np.ndarray, head: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows, y, ids = labelled(df, head)
    return (x[rows.index.to_numpy()] if head == "set" else x), y, ids


def _verdict_rate(df: pd.DataFrame, col: str, margin: float = 0.25) -> dict:
    """When the day score favours a player, how often did that player win each set, and the match?"""
    d = df[col].to_numpy(dtype=float)
    fav = np.where(d > margin, 1, np.where(d < -margin, 2, 0))
    keep = fav > 0
    sub = df[keep]
    f = fav[keep]
    sets = sum(str(sw).count(str(k)) for sw, k in zip(sub.set_winners, f))
    n_sets = int(sub.set_winners.str.len().sum())
    match = int((sub.winner.to_numpy() == f).sum())
    return {"n_matches": int(keep.sum()), "share": float(keep.mean()), "sets": sets, "n_sets": n_sets,
            "set_rate": sets / n_sets if n_sets else None, "match": match,
            "match_rate": match / len(sub) if len(sub) else None}


def train(feats: pd.DataFrame, log=print, quick: bool = False) -> dict:
    feats = feats.sort_values("date").reset_index(drop=True)
    end = feats.date.max()
    hold_from = end - pd.Timedelta(days=365)
    mid = end - pd.Timedelta(days=182)
    tr, ho = feats[feats.date < hold_from], feats[feats.date >= hold_from].reset_index(drop=True)
    h1, h2 = ho[ho.date < mid].reset_index(drop=True), ho[ho.date >= mid].reset_index(drop=True)
    log(f"training {len(tr):,} matches, holding out {len(ho):,} (from {hold_from:%Y-%m-%d}; halves {len(h1):,} + {len(h2):,})")

    # 1) the trees with every feature group (does a single model find use for astrology / numerology?)
    candidates = {"statistics": ["stats"], "statistics + astrology": ["stats", "astro"],
                  "statistics + numerology": ["stats", "numerology"],
                  "statistics + astrology + numerology": ["stats", "astro", "numerology"]}
    ablation, per = {}, {}
    for name, groups in candidates.items():
        cols = feature_set(groups)
        res = {}
        for head in ("set", "match"):
            m = fit(tr, head, cols)
            s = score(ho, head, predict_p(m, ho, cols, head))
            res[head] = _clean(s)
            if head == "set":
                per[name] = per_match(s)
        ablation[name] = res
        log(f"  {name}: set log loss {res['set']['log_loss']:.4f}, match {res['match']['log_loss']:.4f}")
    base = per["statistics"]
    gate = {}
    for name in candidates:
        if name != "statistics":
            d = (per[name] - base).dropna()
            gate[name] = {"delta": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}
    chosen, best = "statistics", 0.0
    for name, g in gate.items():
        if g["se"] and g["delta"] < -g["se"] and g["delta"] < best:
            chosen, best = name, g["delta"]
    groups = candidates[chosen]
    cols = feature_set(groups)
    log(f"chosen features for the trees: {chosen}")

    # 2) hyperparameters
    tuning = []
    for params in (GRID[:2] if quick else GRID):
        m = fit(tr, "set", cols, params)
        s = score(ho, "set", predict_p(m, ho, cols, "set"))
        tuning.append({"params": params, "log_loss": s["log_loss"]})
        log(f"  {params}: {s['log_loss']:.4f}")
    params = min(tuning, key=lambda t: t["log_loss"])["params"]

    # 3) statistics heads on the training years → probabilities on the held-out year
    heads_tr = {h: fit(tr, h, cols, params) for h in HEADS}
    p_ho = {h: predict_p(heads_tr[h], ho, cols, h) for h in HEADS}

    # 4) machine-learned astrology and numerology: each alone, then on top of the statistics
    learned = {}
    side_models = {}
    for key, scols in (("astro", ASTRO_COLS), ("numerology", NUM_COLS)):
        tries = []
        for kind, C in (("logistic", 0.003), ("logistic", 0.03), ("logistic", 0.3), ("trees", None)):
            m = fit_side(tr, scols, kind, C or 0.03)
            x1 = side_logit(m, h1, scols)
            pr, y, _ = _set_level(h1, _sig(x1), "set")
            tries.append({"kind": kind, "C": C, "log_loss_h1": float(_ll(y, pr).mean()), "_m": m})
        pick = min(tries, key=lambda t: t["log_loss_h1"])
        m = pick["_m"]
        x2 = side_logit(m, h2, scols)
        pr, y, _ = _set_level(h2, _sig(x2), "set")
        learned[key] = {"kind": pick["kind"], "C": pick["C"], "tried": [{k: v for k, v in t.items() if k != "_m"} for t in tries],
                        "alone_h2": {"n_sets": int(len(y)), "log_loss": float(_ll(y, pr).mean()), "coin": float(np.log(2)),
                                     "accuracy": float(((pr > 0.5) == y).mean())}}
        side_models[key] = m
        log(f"  learned {key}: {pick['kind']} C={pick['C']}, alone on unseen sets: accuracy "
            f"{learned[key]['alone_h2']['accuracy']:.3f}, log loss {learned[key]['alone_h2']['log_loss']:.4f} (coin 0.6931)")
    edge = {k: side_logit(side_models[k], ho, c) for k, c in (("astro", ASTRO_COLS), ("numerology", NUM_COLS))}

    # 5) the combiner: statistics + learned astrology + learned numerology, fitted on the first half of the
    #    held-out year, judged on the second half against the statistics alone (fitted the same way)
    is1 = (ho.date < mid).to_numpy()
    combiner, combo_eval = {}, {}
    for h in HEADS:
        intercept = h == "one_set"
        X = np.c_[_logit(p_ho[h]), edge["astro"], edge["numerology"]]
        Xs, y, ids = _set_level(ho, X, h)
        part1 = np.isin(ids, ho.id[is1].to_numpy())
        full = LogisticRegression(C=1.0, fit_intercept=intercept, max_iter=1000).fit(Xs[part1], y[part1])
        only = LogisticRegression(C=1.0, fit_intercept=intercept, max_iter=1000).fit(Xs[part1][:, :1], y[part1])
        pf = full.predict_proba(Xs[~part1])[:, 1]
        po = only.predict_proba(Xs[~part1][:, :1])[:, 1]
        d = pd.Series(_ll(y[~part1], pf) - _ll(y[~part1], po)).groupby(ids[~part1]).mean()
        combo_eval[h] = {"with": float(_ll(y[~part1], pf).mean()), "without": float(_ll(y[~part1], po).mean()),
                         "delta": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))),
                         "acc_with": float(((pf > 0.5) == y[~part1]).mean()), "acc_without": float(((po > 0.5) == y[~part1]).mean()),
                         "weights": [float(w) for w in full.coef_[0]]}
        final = LogisticRegression(C=1.0, fit_intercept=intercept, max_iter=1000).fit(Xs, y)
        # keep astrology/numerology weights only where they helped on unseen matches; otherwise zero them
        w = final.coef_[0].copy()
        helps = combo_eval[h]["delta"] < -combo_eval[h]["se"]
        if not helps:
            w[1:] = 0.0
            w[0] = LogisticRegression(C=1.0, fit_intercept=intercept, max_iter=1000).fit(Xs[:, :1], y).coef_[0][0]
        combiner[h] = {"w": [float(x) for x in w], "b": float(final.intercept_[0]) if intercept else 0.0, "astro_num_used": bool(helps)}
        log(f"  combiner {h}: with astrology+numerology {combo_eval[h]['with']:.4f} vs without {combo_eval[h]['without']:.4f}"
            f" (Δ {combo_eval[h]['delta']:+.4f} ± {combo_eval[h]['se']:.4f}) → {'used' if helps else 'not used'}")

    # 6) traditional day verdicts: how often the favoured player won
    verdicts = {"astro": _verdict_rate(ho, "d_astro_rule"), "numerology": _verdict_rate(ho, "d_num_rule", 0.4)}

    # 7) odds → set, first set and at-least-one-set chances (fitted from the match probability, per format)
    maps = {}
    for bo in (3, 5):
        sub = ho[ho.best_of5 == float(bo == 5)].reset_index(drop=True)
        if len(sub) < 200:
            continue
        x = _logit(predict_p(heads_tr["match"], sub, cols, "match"))
        maps[bo] = {}
        for h in ("set", "first", "one_set"):
            xs, y, _ = _set_level(sub, x, h)
            lr = LogisticRegression(C=10.0, fit_intercept=True, max_iter=1000).fit(xs[:, None], y)
            maps[bo][h] = {"a": float(lr.coef_[0][0]), "b": float(lr.intercept_[0])}
    holdout = {}
    for h in HEADS:
        holdout[h] = {"model": _clean(score(ho, h, p_ho[h])), "elo": _clean(score(ho, h, elo_baseline(tr, ho, h)))}
        log(f"  holdout {h}: model {holdout[h]['model']['log_loss']:.4f} vs Elo {holdout[h]['elo']['log_loss']:.4f}, "
            f"accuracy {holdout[h]['model']['accuracy']:.3f}")
    importance = {}
    rng = np.random.default_rng(0)
    ref = holdout["set"]["model"]["log_loss"]
    for g in groups:
        sh = ho.copy()
        for c in GROUPS[g]:
            sh[c] = rng.permutation(sh[c].to_numpy())
        importance[g] = float(score(ho, "set", predict_p(heads_tr["set"], sh, cols, "set"))["log_loss"] - ref)

    # 8) walk-forward by season (statistics trees vs Elo)
    walk = []
    years = sorted(feats.date.dt.year.unique())
    for y in years[-(2 if quick else 4):]:
        t0 = pd.Timestamp(f"{y}-01-01", tz="UTC")
        a, b = feats[feats.date < t0], feats[(feats.date >= t0) & (feats.date < t0 + pd.DateOffset(years=1))].reset_index(drop=True)
        if len(a) < 5000 or len(b) < 500:
            continue
        row = {"season": int(y), "n": int(len(b))}
        for head in ("set", "match"):
            m = fit(a, head, cols, params)
            row[head] = _clean(score(b, head, predict_p(m, b, cols, head)))
            row[head + "_elo"] = _clean(score(b, head, elo_baseline(a, b, head)))
        walk.append(row)
        log(f"  season {y}: set {row['set']['log_loss']:.4f} (Elo {row['set_elo']['log_loss']:.4f})")

    # 9) final models on everything
    heads = {h: fit(feats, h, cols, params) for h in HEADS}
    sides = {"astro": fit_side(feats, ASTRO_COLS, learned["astro"]["kind"], learned["astro"]["C"] or 0.03),
             "numerology": fit_side(feats, NUM_COLS, learned["numerology"]["kind"], learned["numerology"]["C"] or 0.03)}
    version = datetime.now(timezone.utc).strftime("t%Y%m%d%H%M")
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"heads": heads, "cols": cols, "groups": groups, "params": params, "version": version, "sides": sides,
                 "combiner": combiner, "maps": maps, "market_weight": MARKET_WEIGHT}, BUNDLE)
    old = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    report = {"version": version, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "n_matches": int(len(feats)), "first_match": f"{feats.date.min():%Y-%m-%d}", "last_match": f"{end:%Y-%m-%d}",
              "holdout_from": f"{hold_from:%Y-%m-%d}", "holdout_mid": f"{mid:%Y-%m-%d}", "n_holdout": int(len(ho)),
              "chosen": chosen, "groups": groups, "params": params, "ablation": ablation, "gate": gate, "tuning": tuning,
              "holdout": holdout, "importance": importance, "walk_forward": walk, "learned": learned,
              "combiner": combiner, "combo_eval": combo_eval, "verdicts": verdicts, "maps": maps,
              "market_weight": MARKET_WEIGHT,
              "history": (old.get("history") or [])[-30:] + [{"version": version, "chosen": chosen,
                                                               "set_log_loss": holdout["set"]["model"]["log_loss"],
                                                               "set_accuracy": holdout["set"]["model"]["accuracy"],
                                                               "n_matches": int(len(feats))}]}
    REPORT.write_text(json.dumps(report, indent=1, default=float))
    return report


_CACHE: dict = {}


def load():
    if not BUNDLE.exists():
        return None
    mt = BUNDLE.stat().st_mtime
    if _CACHE.get("mt") != mt:
        _CACHE.update(mt=mt, bundle=joblib.load(BUNDLE))
    return _CACHE["bundle"]


def load_report() -> dict:
    return json.loads(REPORT.read_text()) if REPORT.exists() else {}


MARKET_WEIGHT = 0.6     # share of the odds in the expected figure until the live record can estimate it


def market_probs(odds_a: float, odds_b: float, best_of: int, maps: dict) -> dict | None:
    """Bookmaker odds (decimal, two-way) → margin-free match chance, then set / first set / at least one set."""
    try:
        ia, ib = 1 / float(odds_a), 1 / float(odds_b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if not (ia > 0 and ib > 0):
        return None
    pa = ia / (ia + ib)
    mp = maps.get(best_of) or maps.get(str(best_of)) or maps.get(3) or maps.get("3")
    out = {"a_match": pa, "b_match": 1 - pa, "overround": ia + ib - 1}
    if mp:
        xa, xb = _logit(pa), _logit(1 - pa)
        for h in ("set", "first"):
            out[f"a_{h}"] = float(_sig(mp[h]["a"] * xa))      # symmetric: no intercept
            out[f"b_{h}"] = 1 - out[f"a_{h}"]
        out["a_one_set"] = float(_sig(mp["one_set"]["a"] * xa + mp["one_set"]["b"]))
        out["b_one_set"] = float(_sig(mp["one_set"]["a"] * xb + mp["one_set"]["b"]))
    return out


def predict(frow: dict, bundle=None, odds: tuple | None = None) -> dict | None:
    """Probabilities for both players from one feature row (player 1 = A):
    p (statistics), the learned astrology/numerology edges, 'combined' (statistics + learned astrology +
    numerology, as weighted by the combiner), 'market' (from odds, if given) and 'expected' (combined blended
    with the market when there are odds: the headline figure)."""
    bundle = bundle or load()
    if bundle is None:
        return None
    df = pd.DataFrame([frow])
    for c in set(bundle["cols"]) | set(ASTRO_COLS) | set(NUM_COLS):
        if c not in df:
            df[c] = np.nan
    cols = bundle["cols"]
    out = {"version": bundle["version"]}
    for h, m in bundle["heads"].items():
        if h == "one_set":
            out["a_one_set"] = float(m.predict_proba(df[cols].to_numpy(dtype=float))[:, 1][0])
            out["b_one_set"] = float(m.predict_proba(flip(df)[cols].to_numpy(dtype=float))[:, 1][0])
        else:
            p = float(predict_p(m, df, cols, h)[0])
            out[f"a_{h}"], out[f"b_{h}"] = p, 1 - p
    sides = bundle.get("sides") or {}
    ea = float(side_logit(sides["astro"], df, ASTRO_COLS)[0]) if "astro" in sides else 0.0
    en = float(side_logit(sides["numerology"], df, NUM_COLS)[0]) if "numerology" in sides else 0.0
    out["astro_edge"], out["num_edge"] = ea, en         # learned log-odds in favour of A
    comb = {}
    cmb = bundle.get("combiner") or {}
    for h in HEADS:
        c = cmb.get(h)
        if not c:
            comb[f"a_{h}"], comb[f"b_{h}"] = out[f"a_{h}"], out[f"b_{h}"]
            continue
        w, b = c["w"], c["b"]
        if h == "one_set":
            comb["a_one_set"] = float(_sig(w[0] * _logit(out["a_one_set"]) + w[1] * ea + w[2] * en + b))
            comb["b_one_set"] = float(_sig(w[0] * _logit(out["b_one_set"]) - w[1] * ea - w[2] * en + b))
        else:
            comb[f"a_{h}"] = float(_sig(w[0] * _logit(out[f"a_{h}"]) + w[1] * ea + w[2] * en))
            comb[f"b_{h}"] = 1 - comb[f"a_{h}"]
    out["combined"] = comb
    out["astro_num_used"] = any(c.get("astro_num_used") for c in cmb.values()) if cmb else False
    mk = market_probs(*odds, int(5 if frow.get("best_of5") else 3), bundle.get("maps") or {}) if odds else None
    out["market"] = mk
    if mk and "a_set" in mk:
        wm = float(bundle.get("market_weight", MARKET_WEIGHT))
        exp = {}
        for h in HEADS:
            for s_ in ("a", "b"):
                exp[f"{s_}_{h}"] = float(_sig((1 - wm) * _logit(comb[f"{s_}_{h}"]) + wm * _logit(mk[f"{s_}_{h}"])))
        for h in ("set", "first", "match"):
            exp[f"b_{h}"] = 1 - exp[f"a_{h}"]
        out["expected"], out["market_weight"] = exp, wm
    else:
        out["expected"], out["market_weight"] = dict(comb), 0.0
    return out


def features_path():
    return DATA / "features.parquet"
