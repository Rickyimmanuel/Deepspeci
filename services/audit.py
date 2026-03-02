"""
Audit Logger Service
Records every analysis run into a JSONL audit trail.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.loader import get_config
from core.logger import get_logger
from models.domain import AnalysisReport

logger = get_logger("deepspeci.services.audit")


class AuditLogger:
    """Appends structured audit entries to a JSONL file."""

    def __init__(self, path: Optional[str] = None):
        audit_path = path or get_config().audit_log_path
        self._path = Path(audit_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log_analysis(self, report: AnalysisReport) -> None:
        """Append a single audit entry for a completed analysis."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "report_id": report.report_id,
            "doc_id": report.doc_id,
            "status": report.status.value,
            "llm_provider": report.llm_provider.value,
            "model_name": report.model_name,
            "input_source": report.input_source.value,
            "duration_seconds": report.duration_seconds,
            "num_ambiguities": len(report.ambiguities),
            "num_gaps": len(report.completeness_gaps),
            "num_warnings": len(report.consistency_warnings),
            "num_stories": len(report.enriched_stories),
            "error": report.error,
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug("Audit entry written for report_id=%s", report.report_id)

    def read_entries(self, limit: int = 50) -> list:
        """Read the last N audit entries (newest first)."""
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").strip().split("\n")
        entries = [json.loads(line) for line in lines if line.strip()]
        return list(reversed(entries[-limit:]))
