from __future__ import annotations
from typing import List
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import BaseParser, ParserError


class LocalManifestParser(BaseParser):
    """Parser for 'LOCAL' format manifests (K1326 / example local layout).

    NOTE: This is a skeleton implementation. Fill in extraction logic using
    page.words coordinates and text groups from PDFDocument.
    """

    manifest_type = ManifestType.LOCAL

    def __init__(self, source_file: Path | None = None):
        super().__init__(source_file=source_file)

    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        records: List[ManifestRecord] = []

        # TODO: implement real parsing using document.pages and word coordinates.
        # This skeleton returns an empty list so CI/tests can import the parser.

        return records
