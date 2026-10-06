"""Mock LLM implementation for deterministic offline testing."""

from __future__ import annotations

import json
import re

from trailear.llm.base import LLM


class MockLLM(LLM):
    """Deterministic LLM that synthesizes journal prose directly from input facts."""

    def __init__(
        self,
        canned_response: str | None = None,
        invent_species: str | None = None,
    ) -> None:
        self.canned_response = canned_response
        self.invent_species = invent_species
        self.call_count = 0

    def generate(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        self.call_count += 1
        if self.canned_response is not None:
            return self.canned_response

        # Attempt to parse species JSON from the prompt
        species_list: list[dict] = []
        match = re.search(r"(\[\s*\{.*\}\s*\])", prompt, re.DOTALL)
        if match:
            try:
                species_list = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        if not species_list:
            body = "I walked quietly along the trail today, listening closely to the rustle of the leaves and the gentle breeze through the branches."
        else:
            descriptions = []
            for sp in species_list:
                common = sp.get("common_name", "bird")
                call = sp.get("call_note")
                habitat = sp.get("habitat")
                count = sp.get("count", 1)

                desc = f"I noted the presence of the {common}"
                if count > 1:
                    desc += f", hearing its distinctive sound {count} times"
                if call:
                    desc += f" with its {call.lower()}"
                if habitat:
                    desc += f", typical of {habitat.lower()}"
                desc += "."
                descriptions.append(desc)

            body = (
                "Setting out onto the trail early in the morning, the woods felt calm and alive. "
                + " ".join(descriptions)
                + " Each call punctuated the quiet air, reminding me of the simple pleasure of tuning into the wild landscape."
            )

        if self.invent_species:
            body += f" High above, I caught a glimpse of a {self.invent_species}."

        return body
