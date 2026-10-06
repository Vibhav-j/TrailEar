"""Builds species.sqlite from the BirdNET label list and data/species_facts.json."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FACTS_PATH = PROJECT_ROOT / "data" / "species_facts.json"
DB_PATH = PROJECT_ROOT / "data" / "species.sqlite"
SCHEMA_PATH = PROJECT_ROOT / "src" / "trailear" / "storage" / "schema.sql"


def init_db(conn: sqlite3.Connection) -> None:
    """Create species table if not exists."""
    conn.execute(
        """
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
    )
    conn.commit()


def try_load_birdnet_labels() -> dict[str, str]:
    """Attempt to load label mappings (scientific -> common) from birdnetlib if installed."""
    labels: dict[str, str] = {}
    try:
        from birdnetlib.analyzer import Analyzer  # lazy import

        analyzer = Analyzer()
        # If analyzer exposes labels
        if hasattr(analyzer, "labels") and analyzer.labels:
            for item in analyzer.labels:
                # Labels in BirdNET often formatted as "Scientific name_Common name"
                if "_" in item:
                    sci, common = item.split("_", 1)
                    labels[sci.strip()] = common.strip()
    except (ImportError, Exception):  # noqa: BLE001, S110
        pass
    return labels


def seed_database() -> int:
    """Seed species.sqlite with BirdNET labels and curated species facts."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    # 1. Base labels from BirdNET (if available)
    birdnet_labels = try_load_birdnet_labels()
    if birdnet_labels:
        print(f"Loaded {len(birdnet_labels)} base labels from BirdNET.")
        for sci, common in birdnet_labels.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO species (scientific_name, common_name, rarity)
                VALUES (?, ?, 'common')
                """,
                (sci, common),
            )

    # 2. Merge curated species facts
    if not FACTS_PATH.exists():
        print(f"[WARN] Facts file not found: {FACTS_PATH}")
        facts_count = 0
    else:
        with open(FACTS_PATH, "r", encoding="utf-8") as fh:
            facts = json.load(fh)
        facts_count = len(facts)
        for f in facts:
            conn.execute(
                """
                INSERT INTO species (scientific_name, common_name, family, habitat, size_note, call_note, rarity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scientific_name) DO UPDATE SET
                    common_name = excluded.common_name,
                    family = COALESCE(excluded.family, species.family),
                    habitat = COALESCE(excluded.habitat, species.habitat),
                    size_note = COALESCE(excluded.size_note, species.size_note),
                    call_note = COALESCE(excluded.call_note, species.call_note),
                    rarity = COALESCE(excluded.rarity, species.rarity)
                """,
                (
                    f.get("scientific_name"),
                    f.get("common_name"),
                    f.get("family"),
                    f.get("habitat"),
                    f.get("size_note"),
                    f.get("call_note"),
                    f.get("rarity", "common"),
                ),
            )
        conn.commit()

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM species")
    total = cur.fetchone()[0]
    conn.close()

    print(f"Seeded {DB_PATH.name}: merged {facts_count} facts, total {total} species.")
    return total


if __name__ == "__main__":
    seed_database()
