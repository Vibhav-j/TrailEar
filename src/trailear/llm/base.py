"""LLM abstract base class."""

from abc import ABC, abstractmethod


class LLM(ABC):
    """Abstract interface for language models."""

    @abstractmethod
    def generate(self, system: str, prompt: str, max_tokens: int = 400) -> str: ...
