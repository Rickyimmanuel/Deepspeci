"""
Workspace Configuration Manager
Persistent workspace.json — saved from UI, loaded at startup.
Overrides .env / config.yaml when present.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("deepspeci.config.workspace")

_WS_PATH = Path(__file__).resolve().parent / "workspace.json"

_DEFAULT: Dict[str, Any] = {
    "llm": {
        "active_provider": "",
        "providers": {}
    },
    "jira": {
        "url": "",
        "email": "",
        "api_token": "",
        "project_key": ""
    },
    "confluence": {
        "url": "",
        "email": "",
        "api_token": "",
        "space_key": ""
    }
}


def _ensure_file() -> Dict[str, Any]:
    if _WS_PATH.exists():
        try:
            data = json.loads(_WS_PATH.read_text(encoding="utf-8"))
            # Merge defaults for any new keys
            for k, v in _DEFAULT.items():
                if k not in data:
                    data[k] = v
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        data[k].setdefault(kk, vv)
            return data
        except Exception as exc:
            logger.warning("Corrupt workspace.json, resetting: %s", exc)
    return json.loads(json.dumps(_DEFAULT))


def load_workspace() -> Dict[str, Any]:
    """Load workspace config from disk."""
    return _ensure_file()


def save_workspace(data: Dict[str, Any]) -> None:
    """Persist workspace config to disk."""
    _WS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _WS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Workspace config saved to %s", _WS_PATH)


# --- Provider management ---

def get_providers(ws: Optional[Dict] = None) -> Dict[str, Dict[str, str]]:
    """Return the dict of all configured LLM providers."""
    ws = ws or load_workspace()
    return ws.get("llm", {}).get("providers", {})


def get_active_provider(ws: Optional[Dict] = None) -> str:
    """Return the name of the active provider, or '' if none."""
    ws = ws or load_workspace()
    return ws.get("llm", {}).get("active_provider", "")


def set_active_provider(name: str) -> None:
    ws = load_workspace()
    ws["llm"]["active_provider"] = name
    save_workspace(ws)


def add_provider(name: str, base_url: str, api_key: str, model_name: str) -> None:
    ws = load_workspace()
    ws["llm"]["providers"][name] = {
        "base_url": base_url,
        "api_key": api_key,
        "model_name": model_name
    }
    save_workspace(ws)


def remove_provider(name: str) -> None:
    ws = load_workspace()
    ws["llm"]["providers"].pop(name, None)
    if ws["llm"]["active_provider"] == name:
        ws["llm"]["active_provider"] = ""
    save_workspace(ws)


def list_provider_names(ws: Optional[Dict] = None) -> List[str]:
    """Always includes 'mock' + any workspace-configured providers."""
    ws = ws or load_workspace()
    names = list(ws.get("llm", {}).get("providers", {}).keys())
    if "mock" not in names:
        names.insert(0, "mock")
    return names


# --- Jira / Confluence shortcuts ---

def get_jira_config(ws: Optional[Dict] = None) -> Dict[str, str]:
    ws = ws or load_workspace()
    return ws.get("jira", {})


def save_jira_config(url: str, email: str, token: str, project_key: str = "") -> None:
    ws = load_workspace()
    ws["jira"] = {"url": url, "email": email, "api_token": token, "project_key": project_key}
    save_workspace(ws)


def get_confluence_config(ws: Optional[Dict] = None) -> Dict[str, str]:
    ws = ws or load_workspace()
    return ws.get("confluence", {})


def save_confluence_config(url: str, email: str, token: str, space_key: str = "") -> None:
    ws = load_workspace()
    ws["confluence"] = {"url": url, "email": email, "api_token": token, "space_key": space_key}
    save_workspace(ws)
