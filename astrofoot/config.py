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

LATTICE_VERSION = "L-2026.1"
VAULT_START = "2025-07-01"    # most recent season: evaluated once per major version
TIMEZONE_OF_SOURCE_TIMES = "Europe/London"   # verified: EPL 15:00 kickoffs stay 15:00 across BST
