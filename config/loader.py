"""
DeepSpeci Configuration Loader
Priority: workspace.json > .env > config.yaml
Warns on missing values — never crashes.
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------

class JiraConfig(BaseModel):
    url: str = ""
    username: str = ""
    token: str = ""
    project_key: str = ""


class ConfluenceConfig(BaseModel):
    url: str = ""
    username: str = ""
    token: str = ""
    space_key: str = ""


class LLMConfig(BaseModel):
    provider: str = ""          # empty = no default assumption
    model_name: str = "gpt-4o"
    api_key: str = ""
    endpoint: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    stream: bool = True
    copilot_token: str = ""
    copilot_endpoint: str = "http://localhost:3000"


class AppConfig(BaseModel):
    app_name: str = "DeepSpeci"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ui_port: int = 8501
    audit_log_path: str = "logs/audit.jsonl"

    jira: JiraConfig = Field(default_factory=JiraConfig)
    confluence: ConfluenceConfig = Field(default_factory=ConfluenceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            warnings.warn(f"Could not parse config YAML ({path}): {exc}")
    return {}


def _apply_workspace(cfg: AppConfig) -> AppConfig:
    """Apply workspace.json overrides (highest priority)."""
    try:
        from config.workspace import load_workspace, get_active_provider, get_providers
        ws = load_workspace()

        # LLM
        active = get_active_provider(ws)
        providers = get_providers(ws)
        if active and active in providers:
            p = providers[active]
            cfg.llm.provider = active
            cfg.llm.endpoint = p.get("base_url", cfg.llm.endpoint)
            cfg.llm.api_key = p.get("api_key", cfg.llm.api_key)
            cfg.llm.model_name = p.get("model_name", cfg.llm.model_name)
        elif active:
            cfg.llm.provider = active

        # Jira
        jira_ws = ws.get("jira", {})
        if jira_ws.get("url"):
            cfg.jira.url = jira_ws["url"]
            cfg.jira.username = jira_ws.get("email", "")
            cfg.jira.token = jira_ws.get("api_token", "")
            cfg.jira.project_key = jira_ws.get("project_key", "")

        # Confluence
        conf_ws = ws.get("confluence", {})
        if conf_ws.get("url"):
            cfg.confluence.url = conf_ws["url"]
            cfg.confluence.username = conf_ws.get("email", "")
            cfg.confluence.token = conf_ws.get("api_token", "")
            cfg.confluence.space_key = conf_ws.get("space_key", "")

    except Exception as exc:
        warnings.warn(f"Could not apply workspace config: {exc}")

    return cfg


def _override_from_env(cfg: AppConfig) -> AppConfig:
    """Apply env-var overrides on top of YAML values."""
    data = cfg.model_dump()

    env_map = {
        "DEEPSPECI_LOG_LEVEL":   ("log_level",),
        "DEEPSPECI_ENVIRONMENT": ("environment",),
        "DEEPSPECI_API_HOST":    ("api_host",),
        "DEEPSPECI_API_PORT":    ("api_port",),
        "DEFAULT_LLM_PROVIDER":  ("llm", "provider"),
        "LLM_PROVIDER":          ("llm", "provider"),
        "LLM_MODEL_NAME":        ("llm", "model_name"),
        "LLM_ENDPOINT":          ("llm", "endpoint"),
        "LLM_TEMPERATURE":       ("llm", "temperature"),
        "LLM_MAX_TOKENS":        ("llm", "max_tokens"),
        "REST_LLM_API_KEY":      ("llm", "api_key"),
        "LLM_API_KEY":           ("llm", "api_key"),
        "OPENAI_API_KEY":        ("llm", "api_key"),
        "COPILOT_ACCESS_TOKEN":  ("llm", "copilot_token"),
        "COPILOT_TOKEN":         ("llm", "copilot_token"),
        "COPILOT_ENDPOINT":      ("llm", "copilot_endpoint"),
        "JIRA_URL":              ("jira", "url"),
        "JIRA_EMAIL":            ("jira", "username"),
        "JIRA_API_TOKEN":        ("jira", "token"),
        "JIRA_PROJECT_KEY":      ("jira", "project_key"),
        "CONFLUENCE_URL":        ("confluence", "url"),
        "CONFLUENCE_API_TOKEN":  ("confluence", "token"),
        "CONFLUENCE_SPACE_KEY":  ("confluence", "space_key"),
    }

    for env_key, path in env_map.items():
        val = os.getenv(env_key)
        if val is not None and val != "":
            target = data
            for p in path[:-1]:
                target = target[p]
            field_val = target.get(path[-1])
            try:
                if isinstance(field_val, int):
                    val = int(val)
                elif isinstance(field_val, float):
                    val = float(val)
            except ValueError:
                pass
            target[path[-1]] = val

    return AppConfig(**data)


def _print_warnings(cfg: AppConfig) -> None:
    if not cfg.llm.provider:
        warnings.warn("[DeepSpeci] No LLM provider configured — will use mock fallback")


@lru_cache(maxsize=1)
def get_config(yaml_path: Optional[str] = None) -> AppConfig:
    """
    Load config with priority: workspace.json > .env > config.yaml.
    Warns on missing values — never crashes.
    """
    base_dir = Path(__file__).resolve().parent.parent
    if yaml_path is None:
        yaml_path = str(base_dir / "config" / "config.yaml")

    raw = _load_yaml(Path(yaml_path))
    cfg = AppConfig(**raw)
    cfg = _override_from_env(cfg)
    cfg = _apply_workspace(cfg)   # workspace wins
    _print_warnings(cfg)
    return cfg


def reload_config(yaml_path: Optional[str] = None) -> AppConfig:
    """Force-reload (clears LRU cache)."""
    get_config.cache_clear()
    return get_config(yaml_path)
