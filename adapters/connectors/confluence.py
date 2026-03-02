"""
Confluence Connector — uses workspace config when available.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx

from adapters.connectors.base import SourceConnector
from core.logger import get_logger
from models.domain import InputSource, StandardRequirementDocument

logger = get_logger("deepspeci.connectors.confluence")


class ConfluenceConnector(SourceConnector):

    def __init__(self):
        self._url = ""
        self._username = ""
        self._token = ""
        self._space_key = ""
        self._configured = False
        self._client: Optional[httpx.AsyncClient] = None
        self._load_config()

    def _load_config(self) -> None:
        try:
            from config.workspace import get_confluence_config
            ccfg = get_confluence_config()
            if ccfg.get("url"):
                self._url = ccfg["url"].rstrip("/")
                self._username = ccfg.get("email", "")
                self._token = ccfg.get("api_token", "")
                self._space_key = ccfg.get("space_key", "")
                self._configured = bool(self._url and self._token)
                if self._configured:
                    return
        except Exception:
            pass
        try:
            from config.loader import get_config
            cfg = get_config().confluence
            self._url = cfg.url.rstrip("/") if cfg.url else ""
            self._username = cfg.username
            self._token = cfg.token
            self._space_key = cfg.space_key
            self._configured = bool(self._url and self._token)
        except Exception:
            pass

    def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self._username, self._token),
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
        return self._client

    async def authenticate(self) -> bool:
        if not self._configured:
            logger.warning("Confluence not configured — running in mock mode")
            return False
        try:
            cli = self._client_instance()
            resp = await cli.get(f"{self._url}/wiki/rest/api/space/{self._space_key}")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Confluence auth failed: %s", exc)
            return False

    async def pull(self, resource_id: str, **kwargs) -> List[StandardRequirementDocument]:
        if not self._configured:
            return self._mock_pull(resource_id)
        try:
            cli = self._client_instance()
            resp = await cli.get(
                f"{self._url}/wiki/rest/api/content/{resource_id}",
                params={"expand": "body.storage,version"},
            )
            resp.raise_for_status()
            page = resp.json()
            title = page.get("title", "Untitled")
            html_body = page.get("body", {}).get("storage", {}).get("value", "")
            plain = self._html_to_text(html_body)
            return [
                StandardRequirementDocument(
                    source=InputSource.CONFLUENCE,
                    title=title,
                    raw_text=plain,
                    metadata={"page_id": resource_id, "mock": False},
                )
            ]
        except Exception as exc:
            logger.error("Confluence pull failed, falling back to mock: %s", exc)
            return self._mock_pull(resource_id)

    async def push(self, resource_id: str, content: str, **kwargs) -> Dict[str, Any]:
        if not self._configured:
            return {"status": "skipped", "reason": "Confluence not configured"}
        try:
            cli = self._client_instance()
            payload = {
                "type": "comment",
                "container": {"id": resource_id, "type": "page"},
                "body": {"storage": {"value": f"<p>{content}</p>", "representation": "storage"}},
            }
            resp = await cli.post(f"{self._url}/wiki/rest/api/content", json=payload)
            resp.raise_for_status()
            return {"status": "pushed", "page_id": resource_id}
        except Exception as exc:
            logger.error("Confluence push failed: %s", exc)
            return {"status": "error", "detail": str(exc)}

    @staticmethod
    def _mock_pull(resource_id: str) -> List[StandardRequirementDocument]:
        logger.info("Returning mock Confluence data for page %s", resource_id)
        return [
            StandardRequirementDocument(
                source=InputSource.CONFLUENCE,
                title=f"Mock Confluence Page {resource_id}",
                raw_text=(
                    "Requirements Specification\n\n"
                    "1. The system shall process user requests within 3 seconds.\n"
                    "2. The system shall support up to 1000 concurrent users.\n"
                    "3. Error messages should be user-friendly.\n"
                    "4. The system must integrate with external APIs."
                ),
                metadata={"page_id": resource_id, "mock": True},
            )
        ]

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
