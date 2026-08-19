from dataclasses import dataclass
from pathlib import Path

import fitz

@dataclass
class PDFWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

@dataclass
class PDFPage:
    page_number: int
    width: float
    height: float
    words: list[PDFWord]

@dataclass
class PDFDocument:
    file_path: Path
    page_count: int
    pages: list[PDFPage]


def read_pdf(file_path: Path) -> PDFDocument:
    if not file_path.exists():
        raise FileNotFoundError(
            f"No se encontró el PDF: {file_path}"
        )

    document = fitz.open(file_path)

    pages: list[PDFPage] = []

    for page_number, page in enumerate(document, start=1):

        raw_words = page.get_text("words")

        words = [
            PDFWord(
                x0=float(word[0]),
                y0=float(word[1]),
                x1=float(word[2]),
                y1=float(word[3]),
                text=str(word[4]),
            )
            for word in raw_words
        ]

        pages.append(
            PDFPage(
                page_number=page_number,
                width=float(page.rect.width),
                height=float(page.rect.height),
                words=words,
            )
        )

    document.close()

    return PDFDocument(
        file_path=file_path,
        page_count=len(pages),
        pages=pages,
    )
