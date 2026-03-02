"""
OCR Adapter Base Interface
Pluggable document-to-text extraction layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class OCRAdapter(ABC):
    """Abstract base for OCR / text-extraction engines."""

    @abstractmethod
    def extract_text(self, file_path: Path, mime_type: Optional[str] = None) -> str:
        """Extract text content from a document or image file."""

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Return True if this adapter can handle the given MIME type."""
