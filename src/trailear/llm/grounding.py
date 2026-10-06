"""Grounding validation and retry logic for LLM-generated journals."""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import TYPE_CHECKING

from trailear.llm.prompts import build_journal_prompt, build_template_summary
from trailear.storage.db import DEFAULT_SPECIES_DB

if TYPE_CHECKING:
    from pathlib import Path

    from trailear.llm.base import LLM

logger = logging.getLogger(__name__)


def get_all_known_species(db_path: Path | str | None = None) -> list[tuple[str, str]]:
    """Fetch all known (scientific_name, common_name) pairs from species.sqlite."""
    path = db_path or DEFAULT_SPECIES_DB
    try:
        conn = sqlite3.connect(str(path))
        cur = conn.cursor()
        cur.execute("SELECT scientific_name, common_name FROM species")
        rows = cur.fetchall()
        conn.close()
        return [(r[0], r[1]) for r in rows]
    except Exception:
        logger.exception("Failed to load species list for grounding check from %s", path)
        return []


def check_grounding(
    text: str,
    allowed_species: list[dict],
    db_path: Path | str | None = None,
) -> tuple[bool, str | None]:
    """Verify that generated text does not mention any known species not on this walk.

    Returns:
        (is_grounded, ungrounded_name): True and None if grounded;
        False and the ungrounded species name if a violation is detected.
    """
    text_lower = text.lower()

    # Build set of allowed names (both common and scientific)
    allowed_names: set[str] = set()
    for sp in allowed_species:
        if sp.get("common_name"):
            allowed_names.add(sp["common_name"].lower())
        if sp.get("scientific_name"):
            allowed_names.add(sp["scientific_name"].lower())

    all_species = get_all_known_species(db_path)

    # Scan for any known species that is NOT in the allowed list
    for sci, common in all_species:
        # Check common name
        if common.lower() not in allowed_names:
            pattern = rf"\b{re.escape(common.lower())}\b"
            if re.search(pattern, text_lower):
                return False, common

        # Check scientific name
        if sci.lower() not in allowed_names:
            pattern = rf"\b{re.escape(sci.lower())}\b"
            if re.search(pattern, text_lower):
                return False, sci

    return True, None


def generate_grounded_journal(
    llm: LLM,
    species_data: list[dict],
    db_path: Path | str | None = None,
    max_retries: int = 1,
) -> tuple[str, bool]:
    """Generate a field journal with grounding verification.

    If an ungrounded bird is detected in the generated text, regenerates once.
    If the second attempt also fails, falls back to the deterministic template summary.

    Returns:
        (journal_text, used_template_fallback)
    """
    system, prompt = build_journal_prompt(species_data)

    # First generation attempt
    try:
        text = llm.generate(system, prompt)
    except Exception:
        logger.exception("LLM generation error on first attempt; falling back to template")
        return build_template_summary(species_data), True

    is_grounded, invalid_species = check_grounding(text, species_data, db_path=db_path)
    if is_grounded:
        return text, False

    logger.warning(
        "Grounding check failed on attempt 1: invented species '%s'. Retrying...",
        invalid_species,
    )

    # Retry generation once with explicit correction
    for retry in range(1, max_retries + 1):
        allowed_str = ", ".join(sp.get("common_name", "") for sp in species_data)
        retry_prompt = (
            f"{prompt}\n\n"
            f"CORRECTION: Your previous draft mentioned '{invalid_species}', which was NOT detected. "
            f"You must strictly mention ONLY: {allowed_str}."
        )
        try:
            text = llm.generate(system, retry_prompt)
        except Exception:
            logger.exception("LLM generation error on retry %d; falling back to template", retry)
            return build_template_summary(species_data), True

        is_grounded, invalid_species = check_grounding(text, species_data, db_path=db_path)
        if is_grounded:
            return text, False

        logger.warning(
            "Grounding check failed on retry %d: invented species '%s'.",
            retry,
            invalid_species,
        )

    # Fallback to plain template summary
    logger.info("Falling back to deterministic template summary built from database rows.")
    return build_template_summary(species_data), True
