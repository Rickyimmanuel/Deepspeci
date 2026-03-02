"""
Workspace Router
POST /workspace/save
GET  /workspace/load
POST /workspace/test/jira
POST /workspace/test/confluence
POST /workspace/test/llm
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.workspace import (
    load_workspace,
    save_workspace,
    add_provider,
    set_active_provider,
    get_providers,
)
from config.loader import reload_config
from core.logger import get_logger

logger = get_logger("deepspeci.api.routers.workspace")
router = APIRouter(prefix="/workspace", tags=["Workspace"])


class WorkspaceSaveRequest(BaseModel):
    workspace: Dict[str, Any]


class ProviderAddRequest(BaseModel):
    name: str
    base_url: str
    api_key: str
    model_name: str


class TestJiraRequest(BaseModel):
    url: str
    email: str
    api_token: str


class TestConfluenceRequest(BaseModel):
    url: str
    email: str
    api_token: str
    space_key: str = ""


class TestLLMRequest(BaseModel):
    provider_name: str
    base_url: str
    api_key: str
    model_name: str


@router.get("/load")
async def workspace_load():
    return load_workspace()


@router.post("/save")
async def workspace_save(req: WorkspaceSaveRequest):
    save_workspace(req.workspace)
    reload_config()
    return {"status": "saved"}


@router.post("/provider/add")
async def provider_add(req: ProviderAddRequest):
    add_provider(req.name, req.base_url, req.api_key, req.model_name)
    reload_config()
    return {"status": "added", "provider": req.name}


@router.post("/provider/activate")
async def provider_activate(name: str):
    set_active_provider(name)
    reload_config()
    return {"status": "activated", "provider": name}


@router.post("/test/jira")
async def test_jira(req: TestJiraRequest):
    import httpx
    try:
        async with httpx.AsyncClient(
            auth=(req.email, req.api_token),
            headers={"Accept": "application/json"},
            timeout=15.0,
        ) as cli:
            r = await cli.get(f"{req.url.rstrip('/')}/rest/api/3/myself")
            r.raise_for_status()
            user_info = r.json()
            return {
                "status": "connected",
                "user": user_info.get("displayName", user_info.get("emailAddress", "OK"))
            }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/test/confluence")
async def test_confluence(req: TestConfluenceRequest):
    import httpx
    try:
        async with httpx.AsyncClient(
            auth=(req.email, req.api_token),
            headers={"Accept": "application/json"},
            timeout=15.0,
        ) as cli:
            url = f"{req.url.rstrip('/')}/wiki/rest/api/space"
            if req.space_key:
                url += f"/{req.space_key}"
            r = await cli.get(url)
            r.raise_for_status()
            return {"status": "connected"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/test/llm")
async def test_llm(req: TestLLMRequest):
    import httpx
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {req.api_key}",
        }
        payload = {
            "model": req.model_name,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 10,
        }
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.post(req.base_url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"status": "connected", "reply": reply.strip()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
