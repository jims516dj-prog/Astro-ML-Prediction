"""Live track record CLI.

  python scripts/live.py cycle                 # settle finished matches, commit upcoming ones, rebuild report
  python scripts/live.py commit [--horizon 4]  # predictions for fixtures kicking off within N days
  python scripts/live.py settle                # fetch results for predicted matches that have finished
  python scripts/live.py report                # rebuild ledger/TRACK_RECORD.md
  python scripts/live.py verify                # check every ledger record's SHA-256

Offline / manual sources: --fixtures FILE.csv and --results FILE.csv [FILE.csv ...] take
football-data.co.uk-format files instead of downloading them.
After `cycle`, commit and push the ledger/ directory *before* the earliest kickoff.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from astrofoot import live  # noqa: E402


def load_fixtures(a) -> list[dict]:
    if a.fixtures:
        return live.parse_fixtures(live.read_csv_bytes(Path(a.fixtures).read_bytes()))
    out, errors = [], []
    for url in live.FIXTURE_URLS:
        try:
            out += live.parse_fixtures(live.fetch_csv(url))
        except Exception as e:  # noqa: BLE001 - report every source failure, keep going
            errors.append(f"{url}: {type(e).__name__}: {e}")
    if errors:
        print("fixture sources unavailable:\n  " + "\n  ".join(errors), file=sys.stderr)
    if not out and errors:
        raise SystemExit("No fixtures could be downloaded (is www.football-data.co.uk allowed by the network policy?)")
    return out


def load_results(a, now) -> dict:
    res = {}
    if a.results:
        for f in a.results:
            res.update(live.parse_results(live.read_csv_bytes(Path(f).read_bytes())))
        return res
    for url in sorted(live.needed_result_urls(a.ledger, now)):
        try:
            res.update(live.parse_results(live.fetch_csv(url)))
        except Exception as e:  # noqa: BLE001
            print(f"results unavailable: {url}: {type(e).__name__}: {e}", file=sys.stderr)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cycle", "commit", "settle", "report", "verify"])
    ap.add_argument("--fixtures")
    ap.add_argument("--results", nargs="*")
    ap.add_argument("--horizon", type=float, default=4.0)
    ap.add_argument("--ledger", type=Path, default=live.LEDGER)
    ap.add_argument("--now", help="ISO timestamp (testing/replay only)")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    if a.cmd == "verify":
        recs = live.read_predictions(a.ledger) + list(live.read_results(a.ledger).values())
        bad = [r.get("match_key") for r in recs if not live.verify(r)]
        print(f"{len(recs) - len(bad)}/{len(recs)} records verify" + (f"; FAILED: {bad}" if bad else ""))
        raise SystemExit(1 if bad else 0)
    if a.cmd in ("cycle", "settle"):
        n = live.settle(load_results(a, now), now, a.ledger)
        print(f"settled {n} match(es)")
    if a.cmd in ("cycle", "commit"):
        r = live.commit(load_fixtures(a), now, a.horizon, a.ledger)
        print(f"committed {r['committed']} prediction(s)")
        for s in r["skipped"]:
            print("  skipped:", s)
    rep = live.report(a.ledger)
    live.write_report(rep, a.ledger)
    print(f"report: {rep['settled']} settled, {rep['pending']} pending")


if __name__ == "__main__":
    main()
