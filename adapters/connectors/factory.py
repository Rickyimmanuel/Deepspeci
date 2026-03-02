"""
Connector Factory
Resolves source connectors by name from a simple registry.
"""
from __future__ import annotations

from typing import Dict, Type

from adapters.connectors.base import SourceConnector
from core.logger import get_logger

logger = get_logger("deepspeci.connectors.factory")

_REGISTRY: Dict[str, Type[SourceConnector]] = {}


def register_connector(name: str, cls: Type[SourceConnector]) -> None:
    _REGISTRY[name] = cls
    logger.debug("Connector registered: %s -> %s", name, cls.__name__)


def _populate_defaults() -> None:
    from adapters.connectors.jira import JiraConnector
    from adapters.connectors.confluence import ConfluenceConnector

    register_connector("jira", JiraConnector)
    register_connector("confluence", ConfluenceConnector)


def get_connector(name: str) -> SourceConnector:
    """Instantiate a connector by name."""
    if not _REGISTRY:
        _populate_defaults()

    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown connector '{name}'. Registered: {list(_REGISTRY.keys())}"
        )
    logger.info("Instantiating connector: %s", cls.__name__)
    return cls()
