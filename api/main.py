"""
DeepSpeci FastAPI Application
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analyze, connectors, config, workspace
from config.loader import get_config
from core.logger import get_logger

logger = get_logger("deepspeci.api")


def create_app() -> FastAPI:
    cfg = get_config()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.version,
        description="AI-powered Requirement Quality Analysis Platform",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analyze.router)
    app.include_router(connectors.router)
    app.include_router(config.router)
    app.include_router(workspace.router)

    @app.get("/", tags=["Health"])
    async def root():
        return {"app": cfg.app_name, "version": cfg.version, "status": "running", "docs": "/docs"}

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok"}

    logger.info("%s v%s API ready (%s)", cfg.app_name, cfg.version, cfg.environment)
    return app


app = create_app()
