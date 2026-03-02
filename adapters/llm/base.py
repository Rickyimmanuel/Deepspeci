"""
LLM Adapter Base Interface
All LLM adapters must implement this ABC.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class LLMAdapter(ABC):
    """Abstract base class for all LLM provider adapters."""

    @abstractmethod
    async def initialize(self) -> None:
        """Set up connection / authenticate with the LLM provider."""

    @abstractmethod
    async def create_session(self) -> str:
        """Create a conversation / request session. Returns session ID."""

    @abstractmethod
    async def send_prompt(self, prompt: str, session_id: Optional[str] = None) -> str:
        """
        Send a prompt and wait for the full response.
        Returns the complete response text.
        """

    @abstractmethod
    async def stream_response(
        self, prompt: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from the LLM.
        Yields string chunks as they arrive.
        """

    @abstractmethod
    async def close_session(self, session_id: Optional[str] = None) -> None:
        """Clean up session resources."""

    async def __aenter__(self) -> "LLMAdapter":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close_session()
