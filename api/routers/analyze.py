"""
Analysis Router
POST /analyze/text  — analyze plain text
POST /analyze/file  — analyze uploaded file
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.orchestrator import Orchestrator
from core.logger import get_logger
from models.domain import AnalyzeRequest, AnalyzeResponse, InputSource
from services.normalizer import DocumentNormalizer

logger = get_logger("deepspeci.api.routers.analyze")
router = APIRouter(prefix="/analyze", tags=["Analysis"])

_orchestrator = Orchestrator()
_normalizer = DocumentNormalizer()


@router.post("/text", response_model=AnalyzeResponse)
async def analyze_text(request: AnalyzeRequest):
    """Analyse requirements from text, Jira, or Confluence."""
    try:
        report = await _orchestrator.run_analysis(request)
        return AnalyzeResponse(report=report)
    except Exception as exc:
        logger.error("analyze_text error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/file", response_model=AnalyzeResponse)
async def analyze_file(file: UploadFile = File(...)):
    """Upload a file (PDF, DOCX, TXT, MD, image) and analyse."""
    try:
        data = await file.read()
        docs = await _normalizer.from_file_bytes(data, file.filename or "upload")
        report = await _orchestrator.run_analysis_on_doc(docs[0])
        return AnalyzeResponse(report=report)
    except Exception as exc:
        logger.error("analyze_file error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
