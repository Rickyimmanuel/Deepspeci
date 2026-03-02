"""
DeepSpeci Domain Models
Core data structures shared across all layers.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class InputSource(str, Enum):
    MANUAL_TEXT = "manual_text"
    FILE_UPLOAD = "file_upload"
    JIRA = "jira"
    CONFLUENCE = "confluence"


class LLMProvider(str, Enum):
    COPILOT = "copilot"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    MOCK = "mock"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Standard Requirement Document (unified ingestion result)
# ---------------------------------------------------------------------------

class StandardRequirementDocument(BaseModel):
    """Normalized document produced by every input path before analysis."""
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: InputSource
    title: str = ""
    raw_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Analysis Report sub-models
# ---------------------------------------------------------------------------

class AmbiguityIssue(BaseModel):
    location: str
    description: str
    suggestion: str


class CompletenessGap(BaseModel):
    missing_aspect: str
    description: str
    recommendation: str


class ConsistencyWarning(BaseModel):
    conflict: str
    description: str
    suggestion: str


class EnrichedUserStory(BaseModel):
    original: str
    enriched: str
    acceptance_criteria: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """Structured output produced by the Requirement Analyzer."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    llm_provider: LLMProvider
    model_name: str
    input_source: InputSource

    ambiguities: List[AmbiguityIssue] = Field(default_factory=list)
    completeness_gaps: List[CompletenessGap] = Field(default_factory=list)
    consistency_warnings: List[ConsistencyWarning] = Field(default_factory=list)
    enriched_stories: List[EnrichedUserStory] = Field(default_factory=list)
    summary: str = ""

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    source: InputSource
    text: Optional[str] = None
    jira_issue_key: Optional[str] = None
    confluence_page_id: Optional[str] = None
    llm_provider: Optional[LLMProvider] = None   # overrides config if set
    model_name: Optional[str] = None


class AnalyzeResponse(BaseModel):
    report: AnalysisReport
    message: str = "Analysis complete"


class ConnectorStatus(BaseModel):
    connector: str
    authenticated: bool
    details: str = ""


class PushToJiraRequest(BaseModel):
    issue_key: str
    report: AnalysisReport
