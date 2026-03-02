"""
LLM Adapter Factory
create_llm(provider_name) resolves adapters dynamically.
Reads from workspace config first, then falls back to mock.
"""
from __future__ import annotations

from typing import Dict, Optional, Type

from adapters.llm.base import LLMAdapter
from core.logger import get_logger

logger = get_logger("deepspeci.adapters.llm.factory")

_REGISTRY: Dict[str, Type[LLMAdapter]] = {}


def register_adapter(name: str, cls: Type[LLMAdapter]) -> None:
    _REGISTRY[name] = cls
    logger.debug("LLM adapter registered: %s -> %s", name, cls.__name__)


def _populate_defaults() -> None:
    from adapters.llm.mock import MockLLMAdapter
    from adapters.llm.rest import RESTLLMAdapter
    from adapters.llm.copilot import CopilotAdapter

    register_adapter("mock", MockLLMAdapter)
    register_adapter("openai", RESTLLMAdapter)
    register_adapter("azure_openai", RESTLLMAdapter)
    register_adapter("ollama", RESTLLMAdapter)
    register_adapter("rest", RESTLLMAdapter)
    register_adapter("copilot", CopilotAdapter)


def create_llm(provider: Optional[str] = None) -> LLMAdapter:
    """
    Instantiate the LLM adapter for the given provider.
    Priority: explicit arg > workspace active_provider > mock
    """
    if not _REGISTRY:
        _populate_defaults()

    # Determine provider
    if not provider:
        try:
            from config.workspace import get_active_provider
            provider = get_active_provider() or ""
        except Exception:
            provider = ""

    if not provider:
        try:
            from config.loader import get_config
            provider = get_config().llm.provider or ""
        except Exception:
            provider = ""

    if not provider:
        provider = "mock"

    # Check workspace for custom REST providers not in built-in registry
    cls = _REGISTRY.get(provider)
    if cls is None:
        # Treat unknown providers as custom REST endpoints
        try:
            from config.workspace import get_providers
            ws_providers = get_providers()
            if provider in ws_providers:
                from adapters.llm.rest import RESTLLMAdapter
                cls = RESTLLMAdapter
                logger.info("Using generic REST adapter for custom provider '%s'", provider)
        except Exception:
            pass

    if cls is None:
        logger.warning("Unknown provider '%s' — falling back to mock", provider)
        cls = _REGISTRY["mock"]

    logger.info("Instantiating LLM adapter: %s (provider=%s)", cls.__name__, provider)
    return cls(provider_override=provider)


get_llm_adapter = create_llm
