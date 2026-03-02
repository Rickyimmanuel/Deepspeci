"""
Config Router
GET /config/status — current config & registered providers
"""
from __future__ import annotations

from fastapi import APIRouter

from adapters.llm.factory import _REGISTRY, _populate_defaults
from config.loader import get_config
from core.logger import get_logger

logger = get_logger("deepspeci.api.routers.config")
router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/status")
async def config_status():
    """Return active config (non-secret) and a list of registered providers."""
    if not _REGISTRY:
        _populate_defaults()
    cfg = get_config()
    return {
        "app_name": cfg.app_name,
        "version": cfg.version,
        "environment": cfg.environment,
        "llm_provider": cfg.llm.provider,
        "llm_model": cfg.llm.model_name,
        "registered_providers": list(_REGISTRY.keys()),
        "jira_configured": bool(cfg.jira.url),
        "confluence_configured": bool(cfg.confluence.url),
    }
