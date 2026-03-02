"""
REST LLM Adapter (Enhanced)
Supports OpenAI-compatible endpoints AND custom REST providers.
Reads credentials from workspace.json when available.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

import httpx

from adapters.llm.base import LLMAdapter
from core.logger import get_logger

logger = get_logger("deepspeci.adapters.llm.rest")

_DEFAULT_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "azure_openai": "",
    "ollama": "http://localhost:11434/v1/chat/completions",
}


class RESTLLMAdapter(LLMAdapter):
    """
    Generic REST adapter for any OpenAI-compatible chat/completions API.
    Works with: OpenAI, Azure OpenAI, Ollama, Kimi, Grok, and any custom provider.
    """

    def __init__(self, provider_override: Optional[str] = None):
        self._provider = provider_override or ""
        self._model = ""
        self._api_key = ""
        self._endpoint = ""
        self._temperature = 0.2
        self._max_tokens = 4096
        self._stream = True
        self._client: Optional[httpx.AsyncClient] = None

        self._load_config()

    def _load_config(self) -> None:
        """Load from workspace.json first, then fall back to config loader."""
        loaded = False
        try:
            from config.workspace import get_providers
            providers = get_providers()
            if self._provider in providers:
                p = providers[self._provider]
                self._endpoint = p.get("base_url", "")
                self._api_key = p.get("api_key", "")
                self._model = p.get("model_name", "gpt-4o")
                loaded = True
                logger.debug("REST adapter config loaded from workspace for '%s'", self._provider)
        except Exception:
            pass

        if not loaded:
            try:
                from config.loader import get_config
                cfg = get_config().llm
                self._model = cfg.model_name
                self._api_key = cfg.api_key
                self._endpoint = cfg.endpoint or _DEFAULT_ENDPOINTS.get(self._provider, "")
                self._temperature = cfg.temperature
                self._max_tokens = cfg.max_tokens
                self._stream = cfg.stream
            except Exception:
                pass

        if not self._endpoint:
            self._endpoint = _DEFAULT_ENDPOINTS.get(self._provider, "")

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _payload(self, prompt: str, stream: bool) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": stream,
        }

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)
        logger.info("RESTLLMAdapter initialised for provider=%s model=%s endpoint=%s",
                     self._provider, self._model, self._endpoint[:60])

    async def create_session(self) -> str:
        return "rest-session-stateless"

    async def send_prompt(self, prompt: str, session_id: Optional[str] = None) -> str:
        assert self._client, "Call initialize() first"
        if not self._endpoint:
            raise RuntimeError(f"No endpoint configured for provider '{self._provider}'")
        payload = self._payload(prompt, stream=False)
        resp = await self._client.post(self._endpoint, headers=self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def stream_response(
        self, prompt: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        assert self._client, "Call initialize() first"
        if not self._endpoint:
            raise RuntimeError(f"No endpoint configured for provider '{self._provider}'")
        payload = self._payload(prompt, stream=True)
        async with self._client.stream("POST", self._endpoint,
                                       headers=self._headers(), json=payload) as resp:
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
