from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument


class ParserError(Exception):
    pass


class BaseParser(ABC):
    """Abstract base class for manifest parsers.

    Parsers accept a PDFDocument (from core.pdf_reader.read_pdf) and must
    return a list of ManifestRecord instances.
    """

    manifest_type: ManifestType

    def __init__(self, source_file: Path | None = None):
        self.source_file = source_file

    @abstractmethod
    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        """Parse the document and return normalized ManifestRecord list.

        Implementations should be tolerant: if a field is missing, leave it
        as None. Raise ParserError for unrecoverable errors.
        """
        raise NotImplementedError


# Small helpers

def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        # Allow formatted numbers with commas
        return float(value.replace(",", ""))
    except Exception:
        return None
