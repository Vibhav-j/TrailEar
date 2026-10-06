"""Journal orchestration: queries walk data, enriches facts, and generates journal."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trailear.llm import get_llm
from trailear.llm.grounding import generate_grounded_journal
from trailear.storage.db import end_walk, get_walk, lookup_species

if TYPE_CHECKING:
    from pathlib import Path

    from trailear.llm.base import LLM

logger = logging.getLogger(__name__)


def generate_and_save_journal(
    walk_id: int,
    llm: LLM | None = None,
    db_path: Path | str | None = None,
    species_db_path: Path | str | None = None,
) -> str | None:
    """Generate field journal prose from walk sightings and store it in walks.sqlite.

    1. Fetches walk and its sightings from database.
    2. Groups sightings by species and merges curated facts from species.sqlite.
    3. Runs LLM with grounding verification (retrying once, then falling back to template).
    4. Persists the journal text into the walk record.

    Returns the generated journal text, or None if the walk was not found.
    """
    walk = get_walk(walk_id, db_path=db_path)
    if walk is None:
        logger.error("Walk #%d not found", walk_id)
        return None

    if not walk.sightings:
        empty_journal = (
            "I took a quiet walk through nature today, taking time to tune into the "
            "ambient sounds of the landscape, though no bird calls were distinctly identified."
        )
        end_walk(walk_id, journal=empty_journal, db_path=db_path)
        return empty_journal

    # Aggregate sightings by species and attach facts from species.sqlite
    species_map: dict[str, dict] = {}
    for s in walk.sightings:
        sci = s.scientific_name
        if sci not in species_map:
            facts = lookup_species(sci, db_path=species_db_path)
            fact = facts[0] if facts else {}
            species_map[sci] = {
                "scientific_name": sci,
                "common_name": s.common_name,
                "count": 1,
                "first_heard_s": s.t_offset_s,
                "family": fact.get("family"),
                "habitat": fact.get("habitat"),
                "size_note": fact.get("size_note"),
                "call_note": fact.get("call_note"),
                "rarity": fact.get("rarity"),
            }
        else:
            species_map[sci]["count"] += 1
            species_map[sci]["first_heard_s"] = min(
                species_map[sci]["first_heard_s"], s.t_offset_s
            )

    species_data = list(species_map.values())

    active_llm = llm or get_llm()
    journal_text, _ = generate_grounded_journal(
        llm=active_llm,
        species_data=species_data,
        db_path=species_db_path,
    )

    end_walk(walk_id, journal=journal_text, db_path=db_path)
    return journal_text
