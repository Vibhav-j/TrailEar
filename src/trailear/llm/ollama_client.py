"""Ollama LLM client integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trailear.config import config
from trailear.llm.base import LLM

if TYPE_CHECKING:
    from ollama import Client

logger = logging.getLogger(__name__)


class OllamaClient(LLM):
    """Client for generating text using a local Ollama server."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model = model or config.llm.model
        self.host = host or config.llm.host
        self.timeout = timeout
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            try:
                import ollama

                self._client = ollama.Client(host=self.host, timeout=self.timeout)
            except ImportError as err:
                raise ImportError(
                    "The 'ollama' Python library is required. Install with 'pip install ollama'"
                ) from err
        return self._client

    def is_available(self) -> bool:
        """Check if the Ollama server is responsive and the model is present."""
        try:
            client = self._get_client()
            client.list()
            return True
        except Exception:  # noqa: BLE001
            return False

    def generate(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        """Send chat prompt to Ollama and return generated text."""
        client = self._get_client()
        try:
            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "num_predict": max_tokens,
                    "temperature": 0.7,
                },
            )
            return response["message"]["content"]
        except Exception as err:
            msg = (
                f"Failed to connect to Ollama at {self.host} (model '{self.model}'): {err}. "
                "Ensure Ollama is running ('ollama serve' or check tray app) "
                "or switch to mock backend via config.yaml (llm.backend: mock)."
            )
            logger.error(msg)
            raise RuntimeError(msg) from err
