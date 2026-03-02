"""
Jira Connector — uses workspace config when available.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from adapters.connectors.base import SourceConnector
from core.logger import get_logger
from models.domain import InputSource, StandardRequirementDocument

logger = get_logger("deepspeci.connectors.jira")


class JiraConnector(SourceConnector):

    def __init__(self):
        self._url = ""
        self._username = ""
        self._token = ""
        self._configured = False
        self._client: Optional[httpx.AsyncClient] = None
        self._load_config()

    def _load_config(self) -> None:
        # workspace.json first
        try:
            from config.workspace import get_jira_config
            jcfg = get_jira_config()
            if jcfg.get("url"):
                self._url = jcfg["url"].rstrip("/")
                self._username = jcfg.get("email", "")
                self._token = jcfg.get("api_token", "")
                self._configured = bool(self._url and self._token)
                if self._configured:
                    logger.debug("Jira config loaded from workspace.json")
                    return
        except Exception:
            pass
        # fallback to config loader / env
        try:
            from config.loader import get_config
            cfg = get_config().jira
            self._url = cfg.url.rstrip("/") if cfg.url else ""
            self._username = cfg.username
            self._token = cfg.token
            self._configured = bool(self._url and self._token)
        except Exception:
            pass

    def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=(self._username, self._token),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=30.0,
            )
        return self._client

    async def authenticate(self) -> bool:
        if not self._configured:
            logger.warning("Jira not configured — running in mock mode")
            return False
        try:
            cli = self._client_instance()
            resp = await cli.get(f"{self._url}/rest/api/3/myself")
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Jira auth failed: %s", exc)
            return False

    async def pull(self, resource_id: str, **kwargs) -> List[StandardRequirementDocument]:
        if not self._configured:
            return self._mock_pull(resource_id)
        try:
            cli = self._client_instance()
            resp = await cli.get(f"{self._url}/rest/api/3/issue/{resource_id}")
            resp.raise_for_status()
            issue = resp.json()
            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            description = self._adf_to_text(fields.get("description") or {})
            raw_text = f"Issue: {resource_id}\nSummary: {summary}\n\nDescription:\n{description}"
            return [
                StandardRequirementDocument(
                    source=InputSource.JIRA,
                    title=f"[{resource_id}] {summary}",
                    raw_text=raw_text,
                    metadata={"issue_key": resource_id,
                              "status": fields.get("status", {}).get("name", ""),
                              "issue_type": fields.get("issuetype", {}).get("name", "")},
                )
            ]
        except Exception as exc:
            logger.error("Jira pull failed, falling back to mock: %s", exc)
            return self._mock_pull(resource_id)

    async def push(self, resource_id: str, content: str, **kwargs) -> Dict[str, Any]:
        if not self._configured:
            return {"status": "skipped", "reason": "Jira not configured"}
        try:
            cli = self._client_instance()
            payload = {
                "body": {"type": "doc", "version": 1,
                         "content": [{"type": "paragraph",
                                      "content": [{"type": "text", "text": content}]}]},
            }
            resp = await cli.post(f"{self._url}/rest/api/3/issue/{resource_id}/comment", json=payload)
            resp.raise_for_status()
            return {"status": "pushed", "issue_key": resource_id}
        except Exception as exc:
            logger.error("Jira push failed: %s", exc)
            return {"status": "error", "detail": str(exc)}

    @staticmethod
    def _mock_pull(resource_id: str) -> List[StandardRequirementDocument]:
        logger.info("Returning mock Jira data for %s", resource_id)
        return [
            StandardRequirementDocument(
                source=InputSource.JIRA,
                title=f"[{resource_id}] Mock Jira Issue",
                raw_text=(
                    f"Issue: {resource_id}\nSummary: Mock Jira Issue\n\n"
                    "Description:\nAs a user I want to be able to log in quickly "
                    "so that I can access the system.\n\n"
                    "Acceptance Criteria:\n- User can enter credentials\n"
                    "- System validates credentials\n- User is redirected to dashboard"
                ),
                metadata={"issue_key": resource_id, "mock": True},
            )
        ]

    def _adf_to_text(self, adf: dict) -> str:
        if not adf:
            return ""
        texts: List[str] = []
        self._walk_adf(adf, texts)
        return "\n".join(texts)

    def _walk_adf(self, node: dict, out: List[str]) -> None:
        if node.get("type") == "text":
            out.append(node.get("text", ""))
        for child in node.get("content", []):
            self._walk_adf(child, out)
