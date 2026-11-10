"""Tennis: set and match forecasts from ESPN history, statistics, astrology and numerology (ML-weighted)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tennis"
MODELS = ROOT / "data" / "models"
LEDGER = ROOT / "ledger" / "tennis"
