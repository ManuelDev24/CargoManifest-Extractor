from __future__ import annotations
from typing import List
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import BaseParser, ParserError


class PuertoRicoManifestParser(BaseParser):
    """Parser for PUERTO_RICO manifests.

    This is a stub to be implemented after detector and structure analysis.
    """

    manifest_type = ManifestType.PUERTO_RICO

    def __init__(self, source_file: Path | None = None):
        super().__init__(source_file=source_file)

    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        # TODO: implement extraction for Puerto Rico layout
        return []
