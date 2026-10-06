"""Tests for journal prompts, grounding check, and template fallback."""

from __future__ import annotations

import sqlite3

import pytest

from trailear.llm.grounding import check_grounding, generate_grounded_journal
from trailear.llm.journal import generate_and_save_journal
from trailear.llm.mock import MockLLM
from trailear.llm.prompts import build_journal_prompt
from trailear.storage.db import (
    add_sighting,
    get_walk,
    init_species_db,
    init_walks_db,
    start_walk,
)


@pytest.fixture
def seeded_dbs(tmp_path):
    walks_db = tmp_path / "walks.sqlite"
    species_db = tmp_path / "species.sqlite"
    init_walks_db(walks_db)
    init_species_db(species_db)

    conn = sqlite3.connect(str(species_db))
    conn.execute(
        """
        INSERT INTO species (scientific_name, common_name, family, habitat, size_note, call_note, rarity)
        VALUES
          ('Turdus merula', 'Eurasian Blackbird', 'Turdidae', 'Woods', '25 cm', 'Flute song', 'common'),
          ('Erithacus rubecula', 'European Robin', 'Muscicapidae', 'Gardens', '14 cm', 'Sweet warble', 'common'),
          ('Tyto alba', 'Barn Owl', 'Tytonidae', 'Farmland', '35 cm', 'Harsh screech', 'uncommon')
        """
    )
    conn.commit()
    conn.close()
    return walks_db, species_db


class TestJournalPrompt:
    def test_prompt_contains_only_provided_species(self):
        species_data = [
            {
                "scientific_name": "Erithacus rubecula",
                "common_name": "European Robin",
                "count": 3,
                "first_heard_s": 12.0,
                "habitat": "Gardens and woodland",
                "call_note": "Sweet warble",
            }
        ]

        system, prompt = build_journal_prompt(species_data)

        # System prompt requirements per section 5
        assert "ONLY" in system
        assert "120" in system and "180" in system
        assert "calm" in system.lower()

        # Prompt must contain the provided species
        assert "European Robin" in prompt
        assert "Erithacus rubecula" in prompt

        # Prompt must NOT contain other species
        assert "Barn Owl" not in prompt
        assert "Eurasian Blackbird" not in prompt
        assert "Great Tit" not in prompt

    def test_grounding_passes_for_clean_text(self, seeded_dbs):
        _, species_db = seeded_dbs
        allowed = [{"common_name": "European Robin", "scientific_name": "Erithacus rubecula"}]

        clean_text = (
            "I walked slowly through the cold damp morning. "
            "A European Robin sang from the hedge with clear notes."
        )
        is_grounded, invalid = check_grounding(clean_text, allowed, db_path=species_db)
        assert is_grounded is True
        assert invalid is None

    def test_grounding_rejects_unallowed_species(self, seeded_dbs):
        _, species_db = seeded_dbs
        allowed = [{"common_name": "European Robin", "scientific_name": "Erithacus rubecula"}]

        hallucinated_text = (
            "I walked through the woods and heard a European Robin. "
            "Suddenly, a Barn Owl flew silently past the tree line."
        )
        is_grounded, invalid = check_grounding(hallucinated_text, allowed, db_path=species_db)
        assert is_grounded is False
        assert invalid == "Barn Owl"

    def test_grounding_rejects_invented_species_and_triggers_template_fallback(self, seeded_dbs):
        _, species_db = seeded_dbs
        allowed = [{"common_name": "European Robin", "scientific_name": "Erithacus rubecula"}]

        # MockLLM that deliberately invents 'Barn Owl'
        bad_llm = MockLLM(invent_species="Barn Owl")

        journal, used_fallback = generate_grounded_journal(
            llm=bad_llm,
            species_data=allowed,
            db_path=species_db,
            max_retries=1,
        )

        # Grounding failed twice (initial + 1 retry), so template fallback must be triggered
        assert bad_llm.call_count == 2
        assert used_fallback is True

        # Fallback text must mention the real species and NOT the invented one
        assert "European Robin" in journal
        assert "Barn Owl" not in journal

    def test_clean_generation_succeeds_without_fallback(self, seeded_dbs):
        _, species_db = seeded_dbs
        allowed = [{"common_name": "European Robin", "scientific_name": "Erithacus rubecula"}]

        good_llm = MockLLM()
        journal, used_fallback = generate_grounded_journal(
            llm=good_llm,
            species_data=allowed,
            db_path=species_db,
        )

        assert good_llm.call_count == 1
        assert used_fallback is False
        assert "European Robin" in journal

    def test_generate_and_save_journal_persists_to_walk(self, seeded_dbs):
        walks_db, species_db = seeded_dbs

        w_id = start_walk(started_at="2026-10-06T08:00:00Z", db_path=walks_db)
        add_sighting(w_id, "Erithacus rubecula", "European Robin", 0.92, 10.0, db_path=walks_db)

        llm = MockLLM()
        journal = generate_and_save_journal(
            walk_id=w_id,
            llm=llm,
            db_path=walks_db,
            species_db_path=species_db,
        )

        assert journal is not None
        assert "European Robin" in journal

        walk = get_walk(w_id, db_path=walks_db)
        assert walk is not None
        assert walk.journal == journal
