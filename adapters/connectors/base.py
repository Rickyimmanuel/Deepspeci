"""
Source Connector Base Interface
All external source connectors must implement this ABC.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from models.domain import StandardRequirementDocument


class SourceConnector(ABC):
    """Abstract base for all external source integration connectors."""

    @abstractmethod
    async def authenticate(self) -> bool:
        """Verify credentials and connectivity. Returns True on success."""

    @abstractmethod
    async def pull(self, resource_id: str, **kwargs) -> List[StandardRequirementDocument]:
        """
        Pull content from the external source.
        resource_id: e.g. a Jira issue key or a Confluence page ID.
        Returns one or more normalized documents.
        """

    @abstractmethod
    async def push(self, resource_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Push enriched content back to the external source.
        Returns a dict with status/details from the remote system.
        """
