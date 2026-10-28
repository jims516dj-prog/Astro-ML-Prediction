"""Download the public source data into data/raw (works on Windows, macOS and Linux).

  python scripts/fetch_data.py          everything (~65 MB): training matches + venue tables
  python scripts/fetch_data.py --live   venue tables only (~5 MB): enough for the app and live forecasts
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
FILES = {
    "stadiums.csv": "https://raw.githubusercontent.com/jokecamp/FootballData/master/other/stadiums-with-GPS-coordinates.csv",
    "csv-cities.csv.gz": "https://github.com/dr5hn/countries-states-cities-database/releases/latest/download/csv-cities.csv.gz",
}
TRAINING = {"Matches.csv": "https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="venue tables only")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    files = FILES if a.live else {**TRAINING, **FILES}
    for name, url in files.items():
        print(f"downloading {name} ...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "astro-football-research/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(RAW / name, "wb") as fh:
            shutil.copyfileobj(r, fh)
    print(f"data/raw ready ({len(files)} files)")


if __name__ == "__main__":
    sys.exit(main())
