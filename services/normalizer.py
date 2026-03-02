"""
Document Normalizer Service
Converts all input paths into StandardRequirementDocument.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Optional

from adapters.connectors.factory import get_connector
from adapters.ocr.default import DefaultOCRAdapter
from core.logger import get_logger
from models.domain import InputSource, StandardRequirementDocument

logger = get_logger("deepspeci.services.normalizer")


class DocumentNormalizer:
    """
    Unified source normaliser.
    Regardless of input path the output is always a list of
    StandardRequirementDocument objects.
    """

    def __init__(self):
        self._ocr = DefaultOCRAdapter()

    async def from_text(self, text: str, title: str = "Manual Input") -> List[StandardRequirementDocument]:
        """Normalize manually pasted text."""
        doc = StandardRequirementDocument(
            source=InputSource.MANUAL_TEXT,
            title=title,
            raw_text=text.strip(),
        )
        logger.info("Normalized manual text input (%d chars)", len(doc.raw_text))
        return [doc]

    async def from_file(self, file_path: Path, original_name: Optional[str] = None) -> List[StandardRequirementDocument]:
        """Normalize an uploaded file (text, PDF, DOCX, image)."""
        text = self._ocr.extract_text(file_path)
        doc = StandardRequirementDocument(
            source=InputSource.FILE_UPLOAD,
            title=original_name or file_path.name,
            raw_text=text,
            metadata={"filename": file_path.name},
        )
        logger.info("Normalized uploaded file %s (%d chars)", file_path.name, len(text))
        return [doc]

    async def from_file_bytes(self, data: bytes, filename: str) -> List[StandardRequirementDocument]:
        """Convenience wrapper: write bytes to a temp file, then extract."""
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return await self.from_file(tmp_path, original_name=filename)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def from_jira(self, issue_key: str) -> List[StandardRequirementDocument]:
        """Pull from Jira via the connector layer."""
        connector = get_connector("jira")
        docs = await connector.pull(issue_key)
        logger.info("Normalized Jira issue %s -> %d docs", issue_key, len(docs))
        return docs

    async def from_confluence(self, page_id: str) -> List[StandardRequirementDocument]:
        """Pull from Confluence via the connector layer."""
        connector = get_connector("confluence")
        docs = await connector.pull(page_id)
        logger.info("Normalized Confluence page %s -> %d docs", page_id, len(docs))
        return docs
