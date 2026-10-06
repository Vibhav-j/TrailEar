"""LLM package for TrailEar journal generation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trailear.config import config

if TYPE_CHECKING:
    from trailear.llm.base import LLM

logger = logging.getLogger(__name__)


def get_llm(backend: str | None = None) -> LLM:
    """Return an LLM instance based on configuration or explicit backend."""
    choice = backend or config.llm.backend

    if choice == "mock":
        from trailear.llm.mock import MockLLM

        return MockLLM()

    if choice == "ollama":
        from trailear.llm.ollama_client import OllamaClient

        client = OllamaClient()
        if not client.is_available():
            logger.info("Ollama server not reachable at %s, degrading to MockLLM", client.host)
            print(f"[INFO] Ollama not reachable at {client.host}, falling back to MockLLM")
            from trailear.llm.mock import MockLLM

            return MockLLM()
        return client

    from trailear.llm.mock import MockLLM

    return MockLLM()
