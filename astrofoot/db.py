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
CREATE TABLE IF NOT EXISTS team_charts (
  team TEXT PRIMARY KEY, founded_date TEXT NOT NULL, founded_time TEXT, place TEXT,
  lat REAL, lon REAL, notes TEXT, based_on TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS venues (
  name TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL, source TEXT NOT NULL, verified_at TEXT
);
CREATE TABLE IF NOT EXISTS my_slips (
  id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS my_slip_picks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, slip_id INTEGER NOT NULL, match_key TEXT NOT NULL, day TEXT NOT NULL,
  kickoff_utc TEXT NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL, league TEXT, selection TEXT NOT NULL,
  label TEXT NOT NULL, p REAL, picked_at TEXT NOT NULL, url TEXT, UNIQUE (slip_id, match_key)
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
    _migrate_picks(con)
    if "section" not in {r[1] for r in con.execute("PRAGMA table_info(my_slips)")}:
        # slips belong to the men's or the women's section; every earlier slip was a men's one
        con.execute("ALTER TABLE my_slips ADD COLUMN section TEXT NOT NULL DEFAULT 'men'")
        con.commit()
    return con


def _migrate_picks(con):
    """One-off: picks saved before slips existed (table my_picks, one per game) become "Slip 1" of their day.
    The old table is kept, renamed my_picks_v1_backup."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='my_picks'").fetchone():
        return
    rows = [dict(r) for r in con.execute("SELECT * FROM my_picks").fetchall()]
    slip_of = {}
    for r in rows:
        if r["day"] not in slip_of:
            slip_of[r["day"]] = con.execute("INSERT INTO my_slips (day, name, created_at) VALUES (?,?,?)",
                                            (r["day"], "Slip 1", r["picked_at"])).lastrowid
        con.execute("INSERT OR IGNORE INTO my_slip_picks (slip_id, match_key, day, kickoff_utc, home, away, league, "
                    "selection, label, p, picked_at, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (slip_of[r["day"]], r["match_key"], r["day"], r["kickoff_utc"], r["home"], r["away"], r.get("league"),
                     r["selection"], r["label"], r.get("p"), r["picked_at"], r.get("url")))
    con.execute("ALTER TABLE my_picks RENAME TO my_picks_v1_backup")
    con.commit()


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


def save_team_chart(con, team: str, founded_date: str, founded_time: str | None, place: str | None,
                    lat: float | None, lon: float | None, based_on: str | None = None, notes: str | None = None):
    """The user's own founding chart for a team; it takes priority over the Wikidata table."""
    con.execute("INSERT OR REPLACE INTO team_charts VALUES (?,?,?,?,?,?,?,?,?)",
                (team.strip(), founded_date, founded_time or None, place, lat, lon, notes, based_on, utcnow()))
    con.commit()


def team_charts(con):
    return [{**dict(r), "date_precision": "day"} for r in con.execute("SELECT * FROM team_charts ORDER BY team")]


# ----------------------------------------------------------------------------- my picks (slips)
def slips(con, day: str | None = None, section: str | None = None) -> list[dict]:
    """Slips, optionally of one day and/or one section ("men" or "women")."""
    q = "SELECT s.*, (SELECT COUNT(*) FROM my_slip_picks p WHERE p.slip_id = s.id) AS n FROM my_slips s"
    cond, args = [], []
    if day:
        cond.append("s.day=?")
        args.append(day)
    if section:
        cond.append("s.section=?")
        args.append(section)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    return [dict(r) for r in con.execute(q + " ORDER BY s.day, s.id", args).fetchall()]


def get_slip(con, slip_id) -> dict | None:
    r = con.execute("SELECT * FROM my_slips WHERE id=?", (slip_id,)).fetchone()
    return dict(r) if r else None


def create_slip(con, day: str, name: str = "", created_at: str | None = None, section: str = "men") -> int:
    """A new slip for `day` in a section; unnamed slips are called "Slip N" (the first free number)."""
    section = section if section in ("men", "women", "tennis") else "men"
    taken = {s["name"] for s in slips(con, day, section)}
    if not name.strip():
        n = 1
        while f"Slip {n}" in taken:
            n += 1
        name = f"Slip {n}"
    sid = con.execute("INSERT INTO my_slips (day, name, created_at, section) VALUES (?,?,?,?)",
                      (day, name.strip()[:60], created_at or utcnow(), section)).lastrowid
    con.commit()
    return sid


def rename_slip(con, slip_id, name: str):
    if name.strip():
        con.execute("UPDATE my_slips SET name=? WHERE id=?", (name.strip()[:60], slip_id))
        con.commit()


def delete_slip(con, slip_id):
    con.execute("DELETE FROM my_slip_picks WHERE slip_id=?", (slip_id,))
    con.execute("DELETE FROM my_slips WHERE id=?", (slip_id,))
    con.commit()


def my_picks(con, day: str | None = None, slip_id=None, section: str | None = None) -> list[dict]:
    """Picks with their slip's name and section; filtered by day, slip and/or section."""
    q = ("SELECT p.*, s.name AS slip_name, s.section AS section FROM my_slip_picks p "
         "JOIN my_slips s ON s.id = p.slip_id")
    cond, args = [], []
    if section:
        cond.append("s.section=?")
        args.append(section)
    if day:
        cond.append("p.day=?")
        args.append(day)
    if slip_id is not None:
        cond.append("p.slip_id=?")
        args.append(slip_id)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    return [dict(r) for r in con.execute(q + " ORDER BY p.kickoff_utc, p.home, s.id", args).fetchall()]


def add_pick(con, slip_id, day: str, p: dict) -> bool:
    """Add a game to a slip (one entry per game per slip). False if the slip already has it."""
    cur = con.execute("INSERT OR IGNORE INTO my_slip_picks (slip_id, match_key, day, kickoff_utc, home, away, league, "
                      "selection, label, p, picked_at, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (slip_id, p["match_key"], day, p["kickoff_utc"], p["home"], p["away"], p.get("league"),
                       p["selection"], p["label"], p.get("p"), p["picked_at"], p.get("url")))
    con.commit()
    return cur.rowcount == 1


def update_pick(con, pick_id, selection: str, label: str, prob, picked_at: str):
    con.execute("UPDATE my_slip_picks SET selection=?, label=?, p=?, picked_at=? WHERE id=?",
                (selection, label, prob, picked_at, pick_id))
    con.commit()


def delete_pick(con, pick_id):
    con.execute("DELETE FROM my_slip_picks WHERE id=?", (pick_id,))
    con.commit()
