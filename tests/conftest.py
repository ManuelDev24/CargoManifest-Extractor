from pathlib import Path
import pytest
import sys
import os

# Ensure src/ is on sys.path so package imports like `parsers` and `core`
# resolve correctly when running tests from the repository root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Minimal lightweight PDF-like data structures used by tests. Avoid importing
# core.pdf_reader to keep tests free of heavy PyMuPDF requirement.

class Word:
    def __init__(self, x0, y0, x1, y1, text):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.text = text


class Page:
    def __init__(self, page_number, words):
        self.page_number = page_number
        self.width = 595
        self.height = 842
        self.words = words


class Document:
    def __init__(self, file_path: Path, pages):
        self.file_path = file_path
        self.page_count = len(pages)
        self.pages = pages


@pytest.fixture
def sample_document(tmp_path):
    # Build a simple document with header lines and one BL line
    words = []
    y = 100
    # Header: NAME OF SHIP MV EXAMPLE (EX)
    header_tokens = ["NAME", "OF", "SHIP", "MV", "EXAMPLE", "(EX)"]
    x = 10
    for t in header_tokens:
        words.append(Word(x, y, x + 20, y + 8, t))
        x += 40

    y += 14
    # VOYAGE line
    words.append(Word(10, y, 60, y + 8, "VOYAGE"))
    words.append(Word(70, y, 140, y + 8, "ABC123"))

    y += 14
    # Some other lines
    words.append(Word(10, y, 200, y + 8, "LOADING PORT (SDQ)"))
    y += 14
    words.append(Word(10, y, 200, y + 8, "DISCHARGE PORT (PRY)"))

    y += 20
    # A BL line
    words.append(Word(10, y, 200, y + 8, "PYRR-0001 1000 KG 2204.62 LBS"))

    page = Page(1, words)
    doc = Document(tmp_path / "test.pdf", [page])
    return doc
