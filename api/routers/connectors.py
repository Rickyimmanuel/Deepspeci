"""
Connector Router — /api/connectors
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from adapters.connectors.factory import get_connector
from core.logger import get_logger
from models.domain import ConnectorStatus, PushToJiraRequest
from services.output import OutputService

logger = get_logger("deepspeci.api.routers.connectors")
router = APIRouter(prefix="/api/connectors", tags=["Connectors"])

_output = OutputService()


@router.get("/jira/status", response_model=ConnectorStatus)
async def jira_status():
    """Check Jira connectivity."""
    try:
        conn = get_connector("jira")
        ok = await conn.authenticate()
        return ConnectorStatus(connector="jira", authenticated=ok)
    except Exception as exc:
        return ConnectorStatus(connector="jira", authenticated=False, details=str(exc))


@router.get("/confluence/status", response_model=ConnectorStatus)
async def confluence_status():
    """Check Confluence connectivity."""
    try:
        conn = get_connector("confluence")
        ok = await conn.authenticate()
        return ConnectorStatus(connector="confluence", authenticated=ok)
    except Exception as exc:
        return ConnectorStatus(connector="confluence", authenticated=False, details=str(exc))


@router.post("/jira/push")
async def push_to_jira(req: PushToJiraRequest):
    """Push an analysis report back to a Jira issue as a comment."""
    try:
        result = await _output.push_to_jira(req.issue_key, req.report)
        return result
    except Exception as exc:
        logger.error("Push-to-Jira error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
