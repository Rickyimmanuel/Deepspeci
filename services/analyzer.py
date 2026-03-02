"""
Requirement Analysis Engine
Calls the LLM adapter, parses response, returns AnalysisReport.
Uses create_llm() from factory.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Optional

from adapters.llm.base import LLMAdapter
from adapters.llm.factory import create_llm
from config.loader import get_config
from core.logger import get_logger
from models.domain import (
    AmbiguityIssue,
    AnalysisReport,
    AnalysisStatus,
    CompletenessGap,
    ConsistencyWarning,
    EnrichedUserStory,
    LLMProvider,
    StandardRequirementDocument,
)

logger = get_logger("deepspeci.services.analyzer")

_SYSTEM_PROMPT = """You are DeepSpeci, an expert Requirement Quality Analyst.

Analyse the following requirement document and return a STRICT JSON object with
exactly these keys (no markdown fences, no extra text):

{
  "ambiguities": [
    {"location": "...", "description": "...", "suggestion": "..."}
  ],
  "completeness_gaps": [
    {"missing_aspect": "...", "description": "...", "recommendation": "..."}
  ],
  "consistency_warnings": [
    {"conflict": "...", "description": "...", "suggestion": "..."}
  ],
  "enriched_stories": [
    {
      "original": "...",
      "enriched": "...",
      "acceptance_criteria": ["..."]
    }
  ],
  "summary": "One paragraph overall summary."
}

Return ONLY valid JSON.

REQUIREMENT DOCUMENT:
"""


class RequirementAnalyzer:

    def __init__(self, llm_adapter: Optional[LLMAdapter] = None, provider: Optional[str] = None):
        self._provider_name = provider or get_config().llm.provider
        self._model_name = get_config().llm.model_name
        self._adapter = llm_adapter

    async def _ensure_adapter(self) -> LLMAdapter:
        if self._adapter is None:
            self._adapter = create_llm(self._provider_name)
            await self._adapter.initialize()
        return self._adapter

    async def analyze(self, doc: StandardRequirementDocument) -> AnalysisReport:
        # Determine enum value safely
        try:
            provider_enum = LLMProvider(self._provider_name)
        except ValueError:
            provider_enum = LLMProvider.MOCK

        report = AnalysisReport(
            doc_id=doc.doc_id,
            llm_provider=provider_enum,
            model_name=self._model_name,
            input_source=doc.source,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        try:
            adapter = await self._ensure_adapter()
            prompt = _SYSTEM_PROMPT + doc.raw_text
            logger.info("Analysing doc_id=%s provider=%s", doc.doc_id, self._provider_name)

            full_response = ""
            try:
                async for chunk in adapter.stream_response(prompt):
                    full_response += chunk
            except NotImplementedError:
                full_response = await adapter.send_prompt(prompt)

            report = self._parse_response(full_response, report)
            report.status = AnalysisStatus.COMPLETED
            report.completed_at = datetime.utcnow()
            logger.info("Analysis complete doc_id=%s (%.1fs)", doc.doc_id, report.duration_seconds or 0)

        except Exception as exc:
            report.status = AnalysisStatus.FAILED
            report.error = f"{type(exc).__name__}: {exc}"
            report.completed_at = datetime.utcnow()
            logger.error("Analysis failed: %s", exc)
            logger.debug(traceback.format_exc())

        return report

    def _parse_response(self, raw: str, report: AnalysisReport) -> AnalysisReport:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            report.summary = cleaned
            return report

        report.ambiguities = [AmbiguityIssue(**i) for i in data.get("ambiguities", [])]
        report.completeness_gaps = [CompletenessGap(**i) for i in data.get("completeness_gaps", [])]
        report.consistency_warnings = [ConsistencyWarning(**i) for i in data.get("consistency_warnings", [])]
        report.enriched_stories = [EnrichedUserStory(**i) for i in data.get("enriched_stories", [])]
        report.summary = data.get("summary", "")
        return report

    async def close(self) -> None:
        if self._adapter:
            await self._adapter.close_session()
