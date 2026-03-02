"""
Mock LLM Adapter
Returns deterministic canned responses — used only as fallback.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

from adapters.llm.base import LLMAdapter
from core.logger import get_logger

logger = get_logger("deepspeci.adapters.llm.mock")

_MOCK_RESPONSE = """
{
  "ambiguities": [
    {
      "location": "Requirement 1",
      "description": "The term 'quickly' is subjective and unmeasurable.",
      "suggestion": "Replace with a concrete SLA, e.g., 'within 2 seconds under normal load'."
    }
  ],
  "completeness_gaps": [
    {
      "missing_aspect": "Error handling",
      "description": "No failure scenarios described.",
      "recommendation": "Add error handling and fallback behaviour requirements."
    }
  ],
  "consistency_warnings": [
    {
      "conflict": "Priority clash",
      "description": "Requirement A states data is optional; Requirement B treats it as mandatory.",
      "suggestion": "Align both requirements to a single source of truth."
    }
  ],
  "enriched_stories": [
    {
      "original": "As a user I want to log in.",
      "enriched": "As a registered user I want to log in using my email and password so that I can access my personalised dashboard securely.",
      "acceptance_criteria": [
        "Given valid credentials, the user is redirected to the dashboard within 2 s.",
        "Given invalid credentials, an error message is shown and no redirect occurs.",
        "After 5 failed attempts the account is temporarily locked."
      ]
    }
  ],
  "summary": "The requirements contain 1 ambiguity, 1 completeness gap, and 1 consistency warning. One user story has been enriched with acceptance criteria."
}
""".strip()


class MockLLMAdapter(LLMAdapter):
    """Canned-response adapter — fallback when no provider is configured."""

    def __init__(self, delay: float = 0.05, provider_override: Optional[str] = None):
        self._delay = delay

    async def initialize(self) -> None:
        logger.info("MockLLMAdapter initialised (no external call)")

    async def create_session(self) -> str:
        return "mock-session-001"

    async def send_prompt(self, prompt: str, session_id: Optional[str] = None) -> str:
        await asyncio.sleep(self._delay * 10)
        return _MOCK_RESPONSE

    async def stream_response(
        self, prompt: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        chunk_size = 40
        for i in range(0, len(_MOCK_RESPONSE), chunk_size):
            await asyncio.sleep(self._delay)
            yield _MOCK_RESPONSE[i : i + chunk_size]

    async def close_session(self, session_id: Optional[str] = None) -> None:
        pass
