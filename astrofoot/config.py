from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
REF = DATA / "ref"
WORK = DATA / "work"          # derived parquet: matches, lattices, engine outputs
MODELS = DATA / "models"      # trained model versions + codex json
DB_PATH = DATA / "app.sqlite3"

for _p in (WORK, MODELS):
    _p.mkdir(parents=True, exist_ok=True)

LATTICE_VERSION = "L-2026.2"    # .1 sky primitives only; .2 adds the three books' testimonies (block C)
VAULT_START = "2025-07-01"      # held out once, for L-2026.1 (data/models/vault.json); spent since then
# Living engine: Engine 4 retrains on all data incl. settled live matches. The one-shot vault has been
# spent, so its seasons join training; the prospective ledger is now the out-of-sample check.
LIVING = True
FIRST_TEST_SEASON = "2020/21"
TIMEZONE_OF_SOURCE_TIMES = "Europe/London"   # verified: EPL 15:00 kickoffs stay 15:00 across BST
