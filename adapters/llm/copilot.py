"""
Copilot Adapter — reads token from workspace.json first.
Falls back to mock if no token is available.
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator, Optional

import httpx

from adapters.llm.base import LLMAdapter
from core.logger import get_logger

logger = get_logger("deepspeci.adapters.llm.copilot")

_MOCK_COPILOT_RESPONSE = json.dumps({
    "ambiguities": [
        {"location": "Requirement 1", "description": "Vague term 'quickly' lacks measurable target.", "suggestion": "Replace with 'within 2 seconds'."}
    ],
    "completeness_gaps": [
        {"missing_aspect": "Error handling", "description": "No failure paths described.", "recommendation": "Add error scenarios and fallback behaviour."}
    ],
    "consistency_warnings": [
        {"conflict": "Data optionality conflict", "description": "Req A says optional, Req B says mandatory.", "suggestion": "Unify to one source of truth."}
    ],
    "enriched_stories": [
        {"original": "As a user I want to log in.",
         "enriched": "As a registered user I want to log in with email and password so that I can access my dashboard securely.",
         "acceptance_criteria": [
             "Given valid creds, user is redirected to dashboard within 2 s.",
             "Given invalid creds, an error message is shown.",
             "After 5 failed attempts, account is temporarily locked."
         ]}
    ],
    "summary": "1 ambiguity, 1 completeness gap, 1 consistency warning detected. 1 user story enriched with acceptance criteria."
}, indent=2)


class CopilotAdapter(LLMAdapter):

    def __init__(self, provider_override: Optional[str] = None):
        self._token = ""
        self._endpoint = "http://localhost:3000"
        self._model = "gpt-4o"
        self._client: Optional[httpx.AsyncClient] = None
        self._mock_mode = True
        self._load_config()

    def _load_config(self) -> None:
        # Try workspace first
        try:
            from config.workspace import get_providers
            providers = get_providers()
            if "copilot" in providers:
                p = providers["copilot"]
                self._token = p.get("api_key", "")
                self._endpoint = p.get("base_url", self._endpoint)
                self._model = p.get("model_name", self._model)
        except Exception:
            pass

        # Fall back to config/env
        if not self._token:
            try:
                from config.loader import get_config
                cfg = get_config().llm
                self._token = cfg.copilot_token
                self._endpoint = cfg.copilot_endpoint or self._endpoint
                self._model = cfg.model_name or self._model
            except Exception:
                pass

        self._mock_mode = not bool(self._token)
        if self._mock_mode:
            logger.warning("CopilotAdapter: no token — running in simulated mode")

    def _rpc_url(self) -> str:
        return f"{self._endpoint.rstrip('/')}/v1/chat/completions"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
            "Editor-Version": "vscode/1.86.0",
            "Copilot-Integration-Id": "deepspeci",
        }

    async def initialize(self) -> None:
        if not self._mock_mode:
            self._client = httpx.AsyncClient(timeout=120.0)
        logger.info("CopilotAdapter initialised (mock=%s)", self._mock_mode)

    async def create_session(self) -> str:
        return str(uuid.uuid4())

    async def send_prompt(self, prompt: str, session_id: Optional[str] = None) -> str:
        if self._mock_mode:
            return _MOCK_COPILOT_RESPONSE
        assert self._client
        payload = {"model": self._model,
                    "messages": [{"role": "user", "content": prompt}], "stream": False}
        resp = await self._client.post(self._rpc_url(), headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "result" in data:
            data = data["result"]
        return data["choices"][0]["message"]["content"]

    async def stream_response(
        self, prompt: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        if self._mock_mode:
            import asyncio
            chunk_size = 60
            for i in range(0, len(_MOCK_COPILOT_RESPONSE), chunk_size):
                await asyncio.sleep(0.02)
                yield _MOCK_COPILOT_RESPONSE[i:i + chunk_size]
            return
        assert self._client
        payload = {"model": self._model,
                    "messages": [{"role": "user", "content": prompt}], "stream": True}
        async with self._client.stream(
            "POST", self._rpc_url(), headers=self._headers(), json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        token = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError):
                        continue

    async def close_session(self, session_id: Optional[str] = None) -> None:
        if self._client:
            await self._client.aclose()
