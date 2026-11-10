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


def train(feats: pd.DataFrame, log=print, quick: bool = False) -> dict:
    feats = feats.sort_values("date").reset_index(drop=True)
    end = feats.date.max()
    hold_from = end - pd.Timedelta(days=365)
    tr, ho = feats[feats.date < hold_from], feats[feats.date >= hold_from].reset_index(drop=True)
    log(f"training {len(tr):,} matches, holding out {len(ho):,} (from {hold_from:%Y-%m-%d})")

    # 1) feature groups, on the 'set' head (the main question) and the match head
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
        if name == "statistics":
            continue
        d = (per[name] - base).dropna()
        gate[name] = {"delta": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else None}
    chosen = "statistics"
    best = 0.0
    for name, g in gate.items():
        if g["se"] and g["delta"] < -g["se"] and g["delta"] < best:
            chosen, best = name, g["delta"]
    groups = candidates[chosen]
    cols = feature_set(groups)
    log(f"chosen features: {chosen}")

    # 2) hyperparameters
    tuning = []
    grid = GRID[:2] if quick else GRID
    for params in grid:
        m = fit(tr, "set", cols, params)
        s = score(ho, "set", predict_p(m, ho, cols, "set"))
        tuning.append({"params": params, "log_loss": s["log_loss"]})
        log(f"  {params}: {s['log_loss']:.4f}")
    params = min(tuning, key=lambda t: t["log_loss"])["params"]

    # holdout scores of every head with the chosen setup, next to the Elo baseline; group importance
    holdout, importance = {}, {}
    for head in HEADS:
        m = fit(tr, head, cols, params)
        p = predict_p(m, ho, cols, head)
        holdout[head] = {"model": _clean(score(ho, head, p)),
                         "elo": _clean(score(ho, head, elo_baseline(tr, ho, head)))}
        if head == "set":
            rng = np.random.default_rng(0)
            ref = holdout[head]["model"]["log_loss"]
            for g in groups:
                sh = ho.copy()
                for c in GROUPS[g]:
                    sh[c] = rng.permutation(sh[c].to_numpy())
                importance[g] = float(score(ho, head, predict_p(m, sh, cols, head))["log_loss"] - ref)
        log(f"  holdout {head}: model {holdout[head]['model']['log_loss']:.4f} "
            f"vs Elo {holdout[head]['elo']['log_loss']:.4f}, accuracy {holdout[head]['model']['accuracy']:.3f}")

    # 3) walk-forward by season
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
        log(f"  season {y}: set {row['set']['log_loss']:.4f} (Elo {row['set_elo']['log_loss']:.4f}), "
            f"accuracy {row['set']['accuracy']:.3f}")

    # 4) final models on everything
    heads = {h: fit(feats, h, cols, params) for h in HEADS}
    version = datetime.now(timezone.utc).strftime("t%Y%m%d%H%M")
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"heads": heads, "cols": cols, "groups": groups, "params": params, "version": version}, BUNDLE)
    old = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    report = {"version": version, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "n_matches": int(len(feats)), "first_match": f"{feats.date.min():%Y-%m-%d}", "last_match": f"{end:%Y-%m-%d}",
              "holdout_from": f"{hold_from:%Y-%m-%d}", "n_holdout": int(len(ho)), "chosen": chosen, "groups": groups,
              "params": params, "ablation": ablation, "gate": gate, "tuning": tuning, "holdout": holdout,
              "importance": importance, "walk_forward": walk,
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


def predict(frow: dict, bundle=None) -> dict | None:
    """Probabilities for both players from one feature row (player 1 = A)."""
    bundle = bundle or load()
    if bundle is None:
        return None
    df = pd.DataFrame([frow])
    for c in bundle["cols"]:
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
    return out


def features_path():
    return DATA / "features.parquet"
