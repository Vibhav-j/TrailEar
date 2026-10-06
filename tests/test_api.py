"""Integration tests for FastAPI endpoints using TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from trailear.api.server import create_app
from trailear.storage.db import (
    add_sighting,
    init_species_db,
    init_walks_db,
    start_walk,
)


@pytest.fixture
def test_app(tmp_path, monkeypatch):
    """Create a FastAPI test application with isolated SQLite databases."""
    walks_db = tmp_path / "walks_test.sqlite"
    species_db = tmp_path / "species_test.sqlite"
    init_walks_db(walks_db)
    init_species_db(species_db)

    import trailear.storage.db as db_mod

    monkeypatch.setattr(db_mod, "DEFAULT_WALKS_DB", walks_db)
    monkeypatch.setattr(db_mod, "DEFAULT_SPECIES_DB", species_db)

    # Seed one test walk and sighting
    w_id = start_walk(started_at="2026-10-06T09:00:00Z", db_path=walks_db)
    add_sighting(w_id, "Turdus merula", "Eurasian Blackbird", 0.92, 5.0, db_path=walks_db)

    app = create_app()
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestAPIEndpoints:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "classifier" in data
        assert "llm" in data
        assert "tts" in data

    def test_list_walks(self, client):
        resp = client.get("/api/walks")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "id" in data[0]
        assert "started_at" in data[0]

    def test_get_walk_detail(self, client):
        resp = client.get("/api/walks/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert "sightings" in data
        assert len(data["sightings"]) == 1
        assert data["sightings"][0]["common_name"] == "Eurasian Blackbird"

    def test_get_walk_not_found(self, client):
        resp = client.get("/api/walks/999999")
        assert resp.status_code == 404

    def test_lifelist(self, client):
        resp = client.get("/api/lifelist")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["scientific_name"] == "Turdus merula"
        assert data[0]["count"] >= 1

    def test_walk_lifecycle_start_and_stop(self, client):
        # Start new walk
        resp_start = client.post("/api/walks/start")
        assert resp_start.status_code == 200
        start_data = resp_start.json()
        assert "walk_id" in start_data
        walk_id = start_data["walk_id"]

        # Stop walk
        resp_stop = client.post(f"/api/walks/{walk_id}/stop")
        assert resp_stop.status_code == 200
        stop_data = resp_stop.json()
        assert stop_data["id"] == walk_id
        assert stop_data["ended_at"] is not None

    def test_static_files_served(self, client):
        resp_root = client.get("/")
        assert resp_root.status_code == 200
        assert "TrailEar" in resp_root.text

        resp_css = client.get("/style.css")
        assert resp_css.status_code == 200

        resp_js = client.get("/app.js")
        assert resp_js.status_code == 200

        resp_sw = client.get("/sw.js")
        assert resp_sw.status_code == 200
