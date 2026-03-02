"""
Orchestrator
input → normalizer → analyzer → audit → report
Reads active provider from workspace — no hardcoded defaults.
"""
from __future__ import annotations

from typing import Optional

from config.loader import reload_config
from core.logger import get_logger
from models.domain import (
    AnalysisReport,
    AnalyzeRequest,
    InputSource,
    StandardRequirementDocument,
)
from services.analyzer import RequirementAnalyzer
from services.audit import AuditLogger
from services.normalizer import DocumentNormalizer

logger = get_logger("deepspeci.api.orchestrator")


class Orchestrator:

    def __init__(self):
        self._normalizer = DocumentNormalizer()
        self._audit = AuditLogger()

    def _resolve_provider(self, request_provider: Optional[str] = None) -> str:
        """Determine provider: explicit > workspace > mock fallback."""
        if request_provider:
            return request_provider
        try:
            from config.workspace import get_active_provider
            active = get_active_provider()
            if active:
                return active
        except Exception:
            pass
        return "mock"

    async def run_analysis(self, request: AnalyzeRequest) -> AnalysisReport:
        reload_config()  # pick up latest workspace changes
        provider = self._resolve_provider(
            request.llm_provider.value if request.llm_provider else None
        )
        docs = await self._normalize(request)
        if not docs:
            raise ValueError("No documents produced from input.")
        return await self._analyze_doc(docs[0], provider)

    async def run_analysis_on_doc(
        self, doc: StandardRequirementDocument, provider: Optional[str] = None
    ) -> AnalysisReport:
        reload_config()
        prov = self._resolve_provider(provider)
        return await self._analyze_doc(doc, prov)

    async def _analyze_doc(self, doc: StandardRequirementDocument, provider: str) -> AnalysisReport:
        analyzer = RequirementAnalyzer(provider=provider)
        report = await analyzer.analyze(doc)
        self._audit.log_analysis(report)
        await analyzer.close()
        return report

    async def _normalize(self, request: AnalyzeRequest):
        if request.source == InputSource.MANUAL_TEXT:
            return await self._normalizer.from_text(request.text or "")
        if request.source == InputSource.JIRA:
            return await self._normalizer.from_jira(request.jira_issue_key or "")
        if request.source == InputSource.CONFLUENCE:
            return await self._normalizer.from_confluence(request.confluence_page_id or "")
        raise ValueError(f"Unsupported source: {request.source}")
