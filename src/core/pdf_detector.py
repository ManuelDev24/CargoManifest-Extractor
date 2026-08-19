from collections import Counter

from .models import ManifestType
from .pdf_reader import PDFDocument


def analyze_pdf_structure(document: PDFDocument) -> dict:
    all_words = []

    for page in document.pages:
        all_words.extend(page.words)

    normalized_words = [
        word.text.strip().upper()
        for word in all_words
        if word.text.strip()
    ]

    counter = Counter(normalized_words)

    return {
        "file": document.file_path.name,
        "pages": document.page_count,
        "total_words": len(all_words),
        "unique_words": len(counter),
        "top_words": counter.most_common(30),
    }
