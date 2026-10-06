"""Tests for pocket mode and TTS sink integration."""

from __future__ import annotations

import sqlite3

import numpy as np

from trailear.classify.mock import MockClassifier
from trailear.detect.manager import DetectionManager
from trailear.pipeline import Pipeline, make_storage_sink, make_tts_sink
from trailear.storage.db import end_walk, get_walk, init_species_db, init_walks_db, start_walk
from trailear.types import Window
from trailear.voice.tts import NullTTS, generate_chime


class SyntheticSource:
    """Emits a controlled sequence of audio windows."""

    def __init__(self, count: int = 5) -> None:
        self.count = count

    def windows(self):
        sr = 48000
        samples = np.zeros(sr * 3, dtype=np.float32)
        for i in range(self.count):
            yield Window(samples=samples, sample_rate=sr, t_start=float(i))


class RareMockClassifier(MockClassifier):
    """Classifier returning a rare bird to test chime trigger."""

    _FAKE_SPECIES = (
        ("Upupa epops", "Eurasian Hoopoe", 0.95),
        ("Turdus merula", "Eurasian Blackbird", 0.90),
    )


class TestPocketMode:
    def test_pocket_mode_speaks_each_species_once_and_stops_cleanly(self, tmp_path, monkeypatch):
        walks_db = tmp_path / "walks_test.sqlite"
        species_db = tmp_path / "species_test.sqlite"
        init_walks_db(walks_db)
        init_species_db(species_db)

        # Seed the species db with a rare and a common species
        conn = sqlite3.connect(str(species_db))
        conn.execute(
            """
            INSERT INTO species (scientific_name, common_name, rarity)
            VALUES
              ('Upupa epops', 'Eurasian Hoopoe', 'rare'),
              ('Turdus merula', 'Eurasian Blackbird', 'common')
            """
        )
        conn.commit()
        conn.close()

        # Monkeypatch DEFAULT_SPECIES_DB and DEFAULT_WALKS_DB so lookup_species and add_sighting use them
        import trailear.storage.db as db_mod

        monkeypatch.setattr(db_mod, "DEFAULT_SPECIES_DB", species_db)
        monkeypatch.setattr(db_mod, "DEFAULT_WALKS_DB", walks_db)

        null_tts = NullTTS()
        null_tts.speak("Walk started")

        walk_id = start_walk(lat=51.5, lon=-0.12, db_path=walks_db)

        # Injected clock: deterministic timestamps matching window t_start
        current_time = 0.0

        def fake_clock() -> float:
            return current_time

        manager = DetectionManager(
            announce_threshold=0.60,
            min_consecutive=2,
            cooldown_s=120.0,
            clock=fake_clock,
        )

        storage_sink = make_storage_sink(walk_id, db_path=walks_db)
        tts_sink = make_tts_sink(
            null_tts,
            speak_only_new_species=True,
            chime_on_rare=True,
        )

        pipeline = Pipeline(
            source=SyntheticSource(count=4),
            classifier=RareMockClassifier(),
            manager=manager,
            sinks=[storage_sink, tts_sink],
        )

        # Run pipeline to completion
        announced = pipeline.run()
        end_walk(walk_id, db_path=walks_db)

        walk = get_walk(walk_id, db_path=walks_db)
        assert walk is not None
        assert walk.ended_at is not None

        # Verify announcements
        # With count=4 windows and min_consecutive=2:
        # Window 0 (t=0): hit 1
        # Window 1 (t=1): hit 2 -> announced!
        # Window 2, 3: suppressed by cooldown
        unique_species = {d.common_name for d in announced}
        assert "Eurasian Hoopoe" in unique_species
        assert "Eurasian Blackbird" in unique_species

        # Check spoken text
        # 1. "Walk started"
        # 2. "Eurasian Hoopoe" (spoken once)
        # 3. "Eurasian Blackbird" (spoken once)
        assert null_tts.spoken[0] == "Walk started"
        assert null_tts.spoken.count("Eurasian Hoopoe") == 1
        assert null_tts.spoken.count("Eurasian Blackbird") == 1

        # Check that chime was played for the rare bird (Eurasian Hoopoe)
        assert null_tts.chimes_played >= 1

        # Post-walk announcement
        n_species = len(unique_species)
        null_tts.speak(f"Walk ended. {n_species} species heard.")
        assert null_tts.spoken[-1] == "Walk ended. 2 species heard."

        # Verify sightings in DB
        assert len(walk.sightings) == 2

    def test_chime_generation(self):
        chime = generate_chime(sample_rate=44100, duration_s=0.2)
        assert isinstance(chime, np.ndarray)
        assert len(chime) == int(44100 * 0.2)
        assert np.max(np.abs(chime)) <= 1.0

    def test_walk_cli_verbose_flags(self):
        from trailear.main import build_parser

        parser = build_parser()

        # Default is not verbose
        args_default = parser.parse_args(["walk"])
        assert args_default.verbose is False

        # -v flag
        args_short = parser.parse_args(["walk", "-v"])
        assert args_short.verbose is True

        # --verbose flag
        args_long = parser.parse_args(["walk", "--verbose"])
        assert args_long.verbose is True
