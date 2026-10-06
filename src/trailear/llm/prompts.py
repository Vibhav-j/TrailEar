"""Prompt templates and fallback text generation for field journals."""

from __future__ import annotations

import json

JOURNAL_SYSTEM_PROMPT = (
    "You are a quiet, observant field naturalist writing a personal walk journal entry.\n"
    "Write in the first person with a calm, reflective tone.\n\n"
    "STRICT RULES:\n"
    "1. Mention ONLY the bird species explicitly provided in the data. Do NOT add, mention, or invent any other birds under any circumstances.\n"
    "2. If a fact (habitat, size, call note) is missing or null, leave it out. Never guess or fabricate information.\n"
    "3. Keep the length between 120 and 180 words.\n"
    "4. Do not include markdown headers or bullet points; write in flowing, contemplative prose."
)


def build_journal_prompt(species_data: list[dict]) -> tuple[str, str]:
    """Build system and user prompt for journal generation."""
    data_json = json.dumps(species_data, indent=2)
    user_prompt = (
        "Here are the bird species detected during today's walk with their observation counts, "
        "first detection times, and known facts:\n\n"
        f"{data_json}\n\n"
        "Please write a calm, first-person nature journal entry (120 to 180 words) reflecting on "
        "these sightings following all system instructions."
    )
    return JOURNAL_SYSTEM_PROMPT, user_prompt


def build_template_summary(species_data: list[dict], started_at: str | None = None) -> str:
    """Deterministic template summary built strictly from database rows.

    Used when grounding fails or when LLM is unavailable.
    """
    if not species_data:
        return (
            "I took a quiet walk through nature today, taking time to tune into the "
            "ambient sounds of the landscape, though no bird calls were distinctly identified."
        )

    sentences = [
        "I went for a quiet walk outdoors today and paid close attention to the birdsong around me."
    ]

    species_summaries = []
    for sp in species_data:
        common = sp.get("common_name", "Unknown bird")
        count = sp.get("count", 1)
        call = sp.get("call_note")
        habitat = sp.get("habitat")

        item = f"{common} ({count} detection{'s' if count > 1 else ''}"
        extra = []
        if call:
            extra.append(f"noted for its {call.lower()}")
        if habitat:
            extra.append(f"typically found in {habitat.lower()}")
        if extra:
            item += f", {'; '.join(extra)}"
        item += ")"
        species_summaries.append(item)

    sentences.append(
        f"Along the path, I recorded sightings of {len(species_data)} bird species: "
        + "; ".join(species_summaries)
        + "."
    )
    sentences.append(
        "Listening closely to each call brought a peaceful focus to the walk, "
        "connecting my steps directly to the living rhythm of the wild."
    )

    return " ".join(sentences)
