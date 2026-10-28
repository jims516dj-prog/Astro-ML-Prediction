"""SQLite store for user-entered matches, the prospective prediction ledger and the edit audit.

The 107k imported matches live in Parquet (data/work); this database holds what users add.
The ledger is append-only: each prediction row stores a SHA-256 of its canonical JSON payload
and whether it was committed before kickoff (spec §12.12).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  team_a TEXT NOT NULL, team_b TEXT NOT NULL, home_side TEXT, sport TEXT, context TEXT,
  kickoff_utc TEXT NOT NULL, time_precision TEXT, venue TEXT, lat REAL, lon REAL, loc_source TEXT,
  odds_a REAL, odds_d REAL, odds_b REAL, odds_source TEXT, odds_type TEXT,
  captain_json TEXT, founding_json TEXT,
  score_a INTEGER, score_b INTEGER, status TEXT NOT NULL DEFAULT 'pending', notes TEXT,
  post_hoc INTEGER NOT NULL DEFAULT 0, stale_analysis INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
  analysis_json TEXT, versions_json TEXT
);
CREATE TABLE IF NOT EXISTS predictions (
  id TEXT PRIMARY KEY, match_id TEXT NOT NULL, engine TEXT NOT NULL, model_version TEXT,
  payload_json TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
  committed_before_kickoff INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT NOT NULL, field TEXT NOT NULL,
  old_value TEXT, new_value TEXT, edited_at TEXT NOT NULL, edited_by TEXT
);
CREATE TABLE IF NOT EXISTS venues (
  name TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL, source TEXT NOT NULL, verified_at TEXT
);
"""

EDITABLE = ["team_a", "team_b", "home_side", "kickoff_utc", "time_precision", "venue", "lat", "lon",
            "odds_a", "odds_d", "odds_b", "odds_source", "odds_type", "context", "notes",
            "score_a", "score_b", "status", "captain_json"]
CHART_INPUTS = {"kickoff_utc", "lat", "lon", "team_a", "team_b", "odds_a", "odds_b", "home_side", "captain_json"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def insert_match(con, rec: dict) -> str:
    mid = rec.get("id") or uuid.uuid4().hex[:12]
    rec = {**rec, "id": mid, "created_at": utcnow(), "updated_at": utcnow()}
    cols = ",".join(rec)
    con.execute(f"INSERT INTO matches ({cols}) VALUES ({','.join('?' * len(rec))})", list(rec.values()))
    con.commit()
    return mid


def get_match(con, mid: str):
    return con.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()


def list_matches(con, include_deleted=False):
    q = "SELECT * FROM matches" + ("" if include_deleted else " WHERE deleted_at IS NULL") + " ORDER BY kickoff_utc DESC"
    return con.execute(q).fetchall()


def update_match(con, mid: str, changes: dict, user: str = "local") -> set[str]:
    """Apply edits with a per-field audit trail. Returns the set of fields that changed."""
    row = get_match(con, mid)
    changed = set()
    for k, v in changes.items():
        if k not in EDITABLE and k not in ("analysis_json", "versions_json", "stale_analysis", "deleted_at"):
            continue
        old = row[k]
        if (old if old is None else str(old)) == (v if v is None else str(v)):
            continue
        changed.add(k)
        if k not in ("analysis_json", "versions_json"):
            con.execute("INSERT INTO audit (match_id, field, old_value, new_value, edited_at, edited_by) "
                        "VALUES (?,?,?,?,?,?)", (mid, k, None if old is None else str(old),
                                                 None if v is None else str(v), utcnow(), user))
        con.execute(f"UPDATE matches SET {k}=?, updated_at=? WHERE id=?", (v, utcnow(), mid))
    con.commit()
    return changed


def audit_trail(con, mid):
    return con.execute("SELECT * FROM audit WHERE match_id=? ORDER BY id", (mid,)).fetchall()


def commit_prediction(con, match_id: str, engine: str, model_version: str, payload: dict,
                      kickoff_utc: str) -> dict:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    created = utcnow()
    before = int(created < datetime.fromisoformat(kickoff_utc).astimezone(timezone.utc).isoformat(timespec="seconds"))
    row = {"id": uuid.uuid4().hex[:16], "match_id": match_id, "engine": engine, "model_version": model_version,
           "payload_json": canonical, "sha256": digest, "created_at": created, "committed_before_kickoff": before}
    con.execute(f"INSERT INTO predictions ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    con.commit()
    return row


def predictions_for(con, mid):
    return con.execute("SELECT * FROM predictions WHERE match_id=? ORDER BY created_at", (mid,)).fetchall()


def ledger(con):
    return con.execute("SELECT p.*, m.team_a, m.team_b, m.score_a, m.score_b, m.status, m.home_side, "
                       "m.odds_a, m.odds_b, m.kickoff_utc FROM predictions p JOIN matches m ON m.id=p.match_id "
                       "ORDER BY p.created_at DESC").fetchall()


def save_venue(con, name, lat, lon, source):
    con.execute("INSERT OR REPLACE INTO venues VALUES (?,?,?,?,?)", (name, lat, lon, source, utcnow()))
    con.commit()


def find_venue(con, name):
    return con.execute("SELECT * FROM venues WHERE lower(name)=lower(?)", (name,)).fetchone()
