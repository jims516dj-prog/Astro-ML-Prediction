"""Tennis pipeline: build (ESPN history + players), features, train (fine-tune + walk-forward), cycle (live)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from astrofoot.tennis import DATA, build, features, live, model  # noqa: E402


def make_features(log=print) -> pd.DataFrame:
    m = live.load_matches()
    pl = live.load_players()
    f, _ = features.history(m, pl, log=log)
    f.to_parquet(DATA / "features.parquet", index=False)
    log(f"features: {len(f):,} matches")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "features", "train", "all", "cycle"])
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.cmd in ("build", "all"):
        print(build.build())
    if a.cmd in ("features", "train", "all"):
        f = make_features()
        if a.cmd != "features":
            rep = model.train(f, quick=a.quick)
            print("chosen:", rep["chosen"], "holdout set log loss:", rep["holdout"]["set"]["model"]["log_loss"])
    if a.cmd == "cycle":
        live.cycle()


if __name__ == "__main__":
    main()
