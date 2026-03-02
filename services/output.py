"""
Output Actions Service
Handles post-analysis actions: push to Jira, download report, format for display.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from adapters.connectors.factory import get_connector
from core.logger import get_logger
from models.domain import AnalysisReport

logger = get_logger("deepspeci.services.output")


class OutputService:
    """Manages the delivery of analysis results."""

    @staticmethod
    async def push_to_jira(issue_key: str, report: AnalysisReport) -> Dict[str, Any]:
        """Format the report and post it as a comment on the specified Jira issue."""
        connector = get_connector("jira")
        formatted = OutputService._format_for_jira(report)
        result = await connector.push(issue_key, formatted)
        logger.info("Report %s pushed to Jira issue %s", report.report_id, issue_key)
        return result

    @staticmethod
    def to_json(report: AnalysisReport) -> str:
        """Return the report as a formatted JSON string for download."""
        return report.model_dump_json(indent=2)

    @staticmethod
    def to_markdown(report: AnalysisReport) -> str:
        """Render the report as a Markdown document."""
        lines = [
            f"# DeepSpeci Analysis Report",
            f"",
            f"**Report ID:** {report.report_id}",
            f"**Document ID:** {report.doc_id}",
            f"**Provider:** {report.llm_provider.value} / {report.model_name}",
            f"**Status:** {report.status.value}",
            f"**Duration:** {report.duration_seconds or 'N/A'}s",
            f"",
            f"## Summary",
            f"",
            report.summary or "_No summary available._",
            f"",
        ]

        if report.ambiguities:
            lines.append("## Ambiguities")
            lines.append("")
            for i, a in enumerate(report.ambiguities, 1):
                lines.append(f"### {i}. {a.location}")
                lines.append(f"- **Issue:** {a.description}")
                lines.append(f"- **Suggestion:** {a.suggestion}")
                lines.append("")

        if report.completeness_gaps:
            lines.append("## Completeness Gaps")
            lines.append("")
            for i, g in enumerate(report.completeness_gaps, 1):
                lines.append(f"### {i}. {g.missing_aspect}")
                lines.append(f"- **Description:** {g.description}")
                lines.append(f"- **Recommendation:** {g.recommendation}")
                lines.append("")

        if report.consistency_warnings:
            lines.append("## Consistency Warnings")
            lines.append("")
            for i, w in enumerate(report.consistency_warnings, 1):
                lines.append(f"### {i}. {w.conflict}")
                lines.append(f"- **Description:** {w.description}")
                lines.append(f"- **Suggestion:** {w.suggestion}")
                lines.append("")

        if report.enriched_stories:
            lines.append("## Enriched User Stories")
            lines.append("")
            for i, s in enumerate(report.enriched_stories, 1):
                lines.append(f"### Story {i}")
                lines.append(f"- **Original:** {s.original}")
                lines.append(f"- **Enriched:** {s.enriched}")
                if s.acceptance_criteria:
                    lines.append(f"- **Acceptance Criteria:**")
                    for ac in s.acceptance_criteria:
                        lines.append(f"  - {ac}")
                lines.append("")

        if report.error:
            lines.append("## Error")
            lines.append(f"```\n{report.error}\n```")

        return "\n".join(lines)

    @staticmethod
    def _format_for_jira(report: AnalysisReport) -> str:
        """Plain-text formatting suitable for a Jira comment."""
        sections = [f"DeepSpeci Analysis Report ({report.report_id})"]
        sections.append(f"Provider: {report.llm_provider.value} / {report.model_name}")
        sections.append(f"Status: {report.status.value}")
        sections.append("")

        if report.summary:
            sections.append(f"Summary: {report.summary}")
            sections.append("")

        if report.ambiguities:
            sections.append("== Ambiguities ==")
            for a in report.ambiguities:
                sections.append(f"  [{a.location}] {a.description} -> {a.suggestion}")
            sections.append("")

        if report.completeness_gaps:
            sections.append("== Completeness Gaps ==")
            for g in report.completeness_gaps:
                sections.append(f"  [{g.missing_aspect}] {g.description} -> {g.recommendation}")
            sections.append("")

        if report.consistency_warnings:
            sections.append("== Consistency Warnings ==")
            for w in report.consistency_warnings:
                sections.append(f"  [{w.conflict}] {w.description} -> {w.suggestion}")
            sections.append("")

        if report.enriched_stories:
            sections.append("== Enriched Stories ==")
            for s in report.enriched_stories:
                sections.append(f"  Original: {s.original}")
                sections.append(f"  Enriched: {s.enriched}")
                for ac in s.acceptance_criteria:
                    sections.append(f"    AC: {ac}")
                sections.append("")

        return "\n".join(sections)
