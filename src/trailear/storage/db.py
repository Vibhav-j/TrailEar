"""SQLite database access layer for species facts and walk logs."""

from __future__ import annotations

import contextlib
import datetime
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from trailear.storage.models import Sighting, Walk

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_WALKS_DB = _PROJECT_ROOT / "data" / "walks.sqlite"
DEFAULT_SPECIES_DB = _PROJECT_ROOT / "data" / "species.sqlite"

WALKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS walks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL, ended_at TEXT,
  lat REAL, lon REAL, journal TEXT
);
CREATE TABLE IF NOT EXISTS sightings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  walk_id INTEGER NOT NULL REFERENCES walks(id),
  scientific_name TEXT NOT NULL, common_name TEXT NOT NULL,
  confidence REAL NOT NULL, t_offset_s REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sightings_walk ON sightings(walk_id);
"""

SPECIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS species (
  scientific_name TEXT PRIMARY KEY,
  common_name     TEXT NOT NULL,
  family          TEXT,
  habitat         TEXT,
  size_note       TEXT,
  call_note       TEXT,
  rarity          TEXT
);
"""


@contextlib.contextmanager
def get_connection(
    target: Path | str | sqlite3.Connection | None,
    default_path: Path,
) -> Iterator[sqlite3.Connection]:
    """Context manager that yields a sqlite3 connection.

    If target is already a sqlite3.Connection, yields it and does not close it.
    If target is a Path or str, connects, enables row factory, and closes on exit.
    """
    if isinstance(target, sqlite3.Connection):
        yield target
        return

    path = target or default_path
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_walks_db(db_path: Path | str | sqlite3.Connection | None = None) -> None:
    """Initialize walks and sightings tables."""
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        conn.executescript(WALKS_SCHEMA)
        conn.commit()


def init_species_db(db_path: Path | str | sqlite3.Connection | None = None) -> None:
    """Initialize species table."""
    with get_connection(db_path, DEFAULT_SPECIES_DB) as conn:
        conn.executescript(SPECIES_SCHEMA)
        conn.commit()


def start_walk(
    started_at: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    db_path: Path | str | sqlite3.Connection | None = None,
) -> int:
    """Create a new walk record, returning the walk_id."""
    init_walks_db(db_path)
    if started_at is None:
        started_at = datetime.datetime.now(datetime.UTC).isoformat()
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO walks (started_at, lat, lon) VALUES (?, ?, ?)",
            (started_at, lat, lon),
        )
        conn.commit()
        return cur.lastrowid


def add_sighting(
    walk_id: int,
    scientific_name: str,
    common_name: str,
    confidence: float,
    t_offset_s: float,
    db_path: Path | str | sqlite3.Connection | None = None,
) -> int:
    """Record a species sighting for a walk, returning sighting_id."""
    init_walks_db(db_path)
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sightings (walk_id, scientific_name, common_name, confidence, t_offset_s)
            VALUES (?, ?, ?, ?, ?)
            """,
            (walk_id, scientific_name, common_name, confidence, t_offset_s),
        )
        conn.commit()
        return cur.lastrowid


def end_walk(
    walk_id: int,
    ended_at: str | None = None,
    journal: str | None = None,
    db_path: Path | str | sqlite3.Connection | None = None,
) -> None:
    """Mark a walk as completed."""
    init_walks_db(db_path)
    if ended_at is None:
        ended_at = datetime.datetime.now(datetime.UTC).isoformat()
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        if journal is not None:
            conn.execute(
                "UPDATE walks SET ended_at = ?, journal = ? WHERE id = ?",
                (ended_at, journal, walk_id),
            )
        else:
            conn.execute(
                "UPDATE walks SET ended_at = ? WHERE id = ?",
                (ended_at, walk_id),
            )
        conn.commit()


def get_walk(
    walk_id: int,
    db_path: Path | str | sqlite3.Connection | None = None,
) -> Walk | None:
    """Get full walk details including sightings."""
    init_walks_db(db_path)
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, started_at, ended_at, lat, lon, journal FROM walks WHERE id = ?",
            (walk_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        cur.execute(
            """
            SELECT id, walk_id, scientific_name, common_name, confidence, t_offset_s
            FROM sightings WHERE walk_id = ? ORDER BY t_offset_s ASC
            """,
            (walk_id,),
        )
        sighting_rows = cur.fetchall()
        sightings = [
            Sighting(
                id=s["id"],
                walk_id=s["walk_id"],
                scientific_name=s["scientific_name"],
                common_name=s["common_name"],
                confidence=s["confidence"],
                t_offset_s=s["t_offset_s"],
            )
            for s in sighting_rows
        ]

        return Walk(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            lat=row["lat"],
            lon=row["lon"],
            journal=row["journal"],
            sightings=sightings,
        )


def list_walks(
    db_path: Path | str | sqlite3.Connection | None = None,
) -> list[dict]:
    """List past walks with sighting counts."""
    init_walks_db(db_path)
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                w.id,
                w.started_at,
                w.ended_at,
                w.lat,
                w.lon,
                w.journal,
                COUNT(s.id) AS sighting_count
            FROM walks w
            LEFT JOIN sightings s ON w.id = s.walk_id
            GROUP BY w.id
            ORDER BY w.started_at DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def life_list(
    db_path: Path | str | sqlite3.Connection | None = None,
) -> list[dict]:
    """Query life list: all species ever detected, first-seen date, count."""
    init_walks_db(db_path)
    with get_connection(db_path, DEFAULT_WALKS_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.scientific_name,
                s.common_name,
                MIN(w.started_at) AS first_seen,
                COUNT(s.id) AS count
            FROM sightings s
            JOIN walks w ON s.walk_id = w.id
            GROUP BY s.scientific_name, s.common_name
            ORDER BY count DESC, s.common_name ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def lookup_species(
    query: str,
    db_path: Path | str | sqlite3.Connection | None = None,
) -> list[dict]:
    """Search species database by scientific or common name."""
    init_species_db(db_path)
    pattern = f"%{query.strip()}%"
    with get_connection(db_path, DEFAULT_SPECIES_DB) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT scientific_name, common_name, family, habitat, size_note, call_note, rarity
            FROM species
            WHERE common_name LIKE ? OR scientific_name LIKE ?
            ORDER BY common_name ASC
            """,
            (pattern, pattern),
        )
        return [dict(row) for row in cur.fetchall()]
