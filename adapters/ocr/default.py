"""
Default OCR / Text Extraction Adapter
Uses built-in Python or lightweight libraries for basic text extraction.
Falls back gracefully when optional dependencies are missing.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from adapters.ocr.base import OCRAdapter
from core.logger import get_logger

logger = get_logger("deepspeci.adapters.ocr.default")


class DefaultOCRAdapter(OCRAdapter):
    """
    Default text extractor with optional support for:
    - .txt / .md  -> direct read
    - .pdf        -> PyPDF2 or pdfplumber (optional)
    - .docx       -> python-docx (optional)
    - images      -> pytesseract (optional)
    """

    _TEXT_TYPES = {
        "text/plain", "text/markdown",
    }
    _PDF_TYPES = {"application/pdf"}
    _DOCX_TYPES = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    _IMAGE_TYPES = {
        "image/png", "image/jpeg", "image/tiff", "image/bmp", "image/webp",
    }

    def supports(self, mime_type: str) -> bool:
        return mime_type in (
            self._TEXT_TYPES | self._PDF_TYPES | self._DOCX_TYPES | self._IMAGE_TYPES
        )

    def extract_text(self, file_path: Path, mime_type: Optional[str] = None) -> str:
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or "application/octet-stream"

        logger.debug("Extracting text from %s (mime=%s)", file_path.name, mime_type)

        if mime_type in self._TEXT_TYPES:
            return file_path.read_text(encoding="utf-8", errors="replace")

        if mime_type in self._PDF_TYPES:
            return self._extract_pdf(file_path)

        if mime_type in self._DOCX_TYPES:
            return self._extract_docx(file_path)

        if mime_type in self._IMAGE_TYPES:
            return self._extract_image(file_path)

        logger.warning("Unsupported mime type %s for file %s", mime_type, file_path.name)
        return ""

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pdf(file_path: Path) -> str:
        try:
            import pdfplumber   # preferred
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return "\n\n".join(pages)
        except ImportError:
            pass
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(file_path))
            return "\n\n".join(
                p.extract_text() or "" for p in reader.pages
            )
        except ImportError:
            logger.error("Install pdfplumber or PyPDF2 for PDF support")
            return "[PDF extraction unavailable — install pdfplumber]"

    @staticmethod
    def _extract_docx(file_path: Path) -> str:
        try:
            from docx import Document
            doc = Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            logger.error("Install python-docx for DOCX support")
            return "[DOCX extraction unavailable — install python-docx]"

    @staticmethod
    def _extract_image(file_path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            return pytesseract.image_to_string(img)
        except ImportError:
            logger.error("Install pytesseract + Pillow for image OCR")
            return "[Image OCR unavailable — install pytesseract]"
