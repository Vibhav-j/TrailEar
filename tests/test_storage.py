"""Tests for SQLite storage layer (walks, sightings, life list, and species lookup)."""

from __future__ import annotations

import sqlite3

import pytest

from trailear.storage.db import (
    add_sighting,
    end_walk,
    get_walk,
    init_species_db,
    init_walks_db,
    life_list,
    list_walks,
    lookup_species,
    start_walk,
)


@pytest.fixture
def walks_db(tmp_path):
    """Provide a path to a temporary walks database."""
    db_file = tmp_path / "walks_test.sqlite"
    init_walks_db(db_file)
    return db_file


@pytest.fixture
def species_db(tmp_path):
    """Provide a path to a temporary species database with seed data."""
    db_file = tmp_path / "species_test.sqlite"
    init_species_db(db_file)

    conn = sqlite3.connect(str(db_file))
    conn.execute(
        """
        INSERT INTO species (scientific_name, common_name, family, habitat, size_note, call_note, rarity)
        VALUES
          ('Turdus merula', 'Eurasian Blackbird', 'Turdidae', 'Gardens and woods', '25 cm', 'Fluting song', 'common'),
          ('Erithacus rubecula', 'European Robin', 'Muscicapidae', 'Gardens', '14 cm', 'Sweet warble', 'common'),
          ('Upupa epops', 'Eurasian Hoopoe', 'Upupidae', 'Dry open plains', '27 cm', 'Oop-oop-oop', 'rare')
        """
    )
    conn.commit()
    conn.close()
    return db_file


class TestWalksStorage:
    def test_start_and_end_walk(self, walks_db):
        walk_id = start_walk(
            started_at="2026-10-06T10:00:00Z",
            lat=51.5,
            lon=-0.12,
            db_path=walks_db,
        )
        assert walk_id > 0

        walk = get_walk(walk_id, db_path=walks_db)
        assert walk is not None
        assert walk.started_at == "2026-10-06T10:00:00Z"
        assert walk.ended_at is None
        assert walk.lat == 51.5
        assert walk.lon == -0.12
        assert len(walk.sightings) == 0

        end_walk(
            walk_id,
            ended_at="2026-10-06T10:30:00Z",
            journal="A lovely morning walk.",
            db_path=walks_db,
        )

        completed = get_walk(walk_id, db_path=walks_db)
        assert completed.ended_at == "2026-10-06T10:30:00Z"
        assert completed.journal == "A lovely morning walk."

    def test_add_sightings_and_get_walk(self, walks_db):
        walk_id = start_walk(started_at="2026-10-06T12:00:00Z", db_path=walks_db)

        s1 = add_sighting(
            walk_id=walk_id,
            scientific_name="Turdus merula",
            common_name="Eurasian Blackbird",
            confidence=0.88,
            t_offset_s=12.5,
            db_path=walks_db,
        )
        s2 = add_sighting(
            walk_id=walk_id,
            scientific_name="Erithacus rubecula",
            common_name="European Robin",
            confidence=0.91,
            t_offset_s=45.0,
            db_path=walks_db,
        )
        assert s1 > 0
        assert s2 > s1

        walk = get_walk(walk_id, db_path=walks_db)
        assert len(walk.sightings) == 2
        assert walk.sightings[0].scientific_name == "Turdus merula"
        assert walk.sightings[1].scientific_name == "Erithacus rubecula"

    def test_list_walks(self, walks_db):
        w1 = start_walk(started_at="2026-10-01T08:00:00Z", db_path=walks_db)
        add_sighting(w1, "Turdus merula", "Blackbird", 0.9, 5.0, db_path=walks_db)
        end_walk(w1, ended_at="2026-10-01T09:00:00Z", db_path=walks_db)

        w2 = start_walk(started_at="2026-10-02T08:00:00Z", db_path=walks_db)
        end_walk(w2, ended_at="2026-10-02T09:00:00Z", db_path=walks_db)

        walks = list_walks(db_path=walks_db)
        assert len(walks) == 2
        # Ordered by started_at DESC
        assert walks[0]["id"] == w2
        assert walks[0]["sighting_count"] == 0
        assert walks[1]["id"] == w1
        assert walks[1]["sighting_count"] == 1

    def test_life_list_aggregation(self, walks_db):
        w1 = start_walk(started_at="2026-10-01T08:00:00Z", db_path=walks_db)
        add_sighting(w1, "Turdus merula", "Eurasian Blackbird", 0.9, 1.0, db_path=walks_db)
        add_sighting(w1, "Erithacus rubecula", "European Robin", 0.8, 2.0, db_path=walks_db)

        w2 = start_walk(started_at="2026-10-05T08:00:00Z", db_path=walks_db)
        add_sighting(w2, "Turdus merula", "Eurasian Blackbird", 0.95, 3.0, db_path=walks_db)

        ll = life_list(db_path=walks_db)
        assert len(ll) == 2

        # Turdus merula should be first with count=2, first_seen from w1
        entry_blackbird = next(e for e in ll if e["scientific_name"] == "Turdus merula")
        assert entry_blackbird["count"] == 2
        assert entry_blackbird["first_seen"] == "2026-10-01T08:00:00Z"

        entry_robin = next(e for e in ll if e["scientific_name"] == "Erithacus rubecula")
        assert entry_robin["count"] == 1
        assert entry_robin["first_seen"] == "2026-10-01T08:00:00Z"


class TestSpeciesStorage:
    def test_lookup_species_by_common_name(self, species_db):
        results = lookup_species("Robin", db_path=species_db)
        assert len(results) == 1
        assert results[0]["scientific_name"] == "Erithacus rubecula"
        assert results[0]["rarity"] == "common"

    def test_lookup_species_by_scientific_name(self, species_db):
        results = lookup_species("Upupa", db_path=species_db)
        assert len(results) == 1
        assert results[0]["common_name"] == "Eurasian Hoopoe"
        assert results[0]["rarity"] == "rare"

    def test_lookup_nonexistent_returns_empty(self, species_db):
        assert lookup_species("Penguin", db_path=species_db) == []
