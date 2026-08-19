from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .models import ManifestType
from .pdf_reader import PDFDocument


RD_CLUES = (
    "NUMERO DE RECIBO",
    "NUMERO DE RECIBO",
    "NÚMERO DE RECIBO",
    "PUERTO DE CARGA",
    "PUERTO DE DESCARGA",
    "PESO",
    "REPUBLICA DOMINICANA",
    "REPUBLICA DOMINICANA)",
)

PUERTO_RICO_CLUES = (
    "VOYAGE NUMBER",
    "LOADING PORT",
    "DISCHARGE PORT",
    "FINAL DESTINATION",
    "DATE OF SAILING FROM POL",
    "NAME OF SHIP",
    "GROSS WEIGHT",
    "AES ITN",
)


SIGNAL_GROUPS = {
    "RD": {
        "weight": 35,
        "patterns": (
            "NUMERO DE RECIBO",
            "NÚMERO DE RECIBO",
            "PUERTO DE CARGA",
            "PUERTO DE DESCARGA",
            "PESO",
            "REPUBLICA DOMINICANA",
        ),
    },
    "PUERTO_RICO": {
        "weight": 35,
        "patterns": (
            "VOYAGE NUMBER",
            "LOADING PORT",
            "DISCHARGE PORT",
            "FINAL DESTINATION",
            "DATE OF SAILING FROM POL",
            "NAME OF SHIP",
            "GROSS WEIGHT",
            "AES ITN",
        ),
    },
}


def _normalize_text(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value)
    cleaned = cleaned.replace("—", " ").replace("–", " ").replace("‐", " ")
    cleaned = re.sub(r"[^A-ZÁÉÍÓÚÜÑ0-9\s]", " ", cleaned.upper())
    return " ".join(cleaned.split())


def _page_text_from_words(page) -> str:
    return " ".join(word.text for word in page.words if word.text)


def _extract_structural_text(document: PDFDocument, max_pages: int = 3, y_ratio: float = 0.42) -> str:
    chunks: list[str] = []

    for page in document.pages[:max_pages]:
        top_band = [
            word.text
            for word in page.words
            if word.y0 <= page.height * y_ratio
        ]
        if top_band:
            chunks.append(" ".join(top_band))

    return " ".join(_normalize_text(part) for part in chunks)


def _score_clues(text: str, clues: tuple[str, ...]) -> int:
    score = 0
    matches: list[str] = []
    for clue in clues:
        normalized = _normalize_text(clue)
        if normalized in text:
            score += 1
            matches.append(clue)
    return score, matches


def _score_signal_group(text: str, group_name: str) -> tuple[int, list[str]]:
    group = SIGNAL_GROUPS[group_name]
    score = 0
    matches: list[str] = []
    for pattern in group["patterns"]:
        normalized_pattern = _normalize_text(pattern)
        if normalized_pattern in text:
            score += 1
            matches.append(pattern)
    return score, matches


def _risk_level(confidence: float, margin: float) -> str:
    if confidence < 55 or margin < 8:
        return "high"
    if confidence < 75 or margin < 18:
        return "medium"
    return "low"


def detect_manifest_type(document: PDFDocument) -> tuple[ManifestType, float]:
    text = _extract_structural_text(document)
    text_full = " ".join(
        _normalize_text(_page_text_from_words(page))
        for page in document.pages[:3]
    )

    rd_score, rd_matches = _score_signal_group(text_full, "RD")
    pr_score, pr_matches = _score_signal_group(text_full, "PUERTO_RICO")

    if rd_score == 0 and pr_score == 0:
        return ManifestType.UNKNOWN, 0.0

    if rd_score >= 2 and rd_score > pr_score:
        margin = rd_score - pr_score
        confidence = min(99.0, 50.0 + rd_score * 12.0 + margin * 4.0)
        if confidence < 60 and margin < 2:
            return ManifestType.UNKNOWN, 0.0
        return ManifestType.RD, round(confidence, 1)

    if pr_score >= 2 and pr_score > rd_score:
        margin = pr_score - rd_score
        confidence = min(99.0, 50.0 + pr_score * 12.0 + margin * 4.0)
        if confidence < 60 and margin < 2:
            return ManifestType.UNKNOWN, 0.0
        return ManifestType.PUERTO_RICO, round(confidence, 1)

    if rd_score == pr_score:
        return ManifestType.UNKNOWN, 0.0

    return ManifestType.UNKNOWN, 0.0


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
    detected_type, confidence = detect_manifest_type(document)
    text = " ".join(
        _normalize_text(_page_text_from_words(page))
        for page in document.pages[:3]
    )
    rd_score, rd_matches = _score_signal_group(text, "RD")
    pr_score, pr_matches = _score_signal_group(text, "PUERTO_RICO")
    margin = abs(rd_score - pr_score)
    risk = _risk_level(confidence, margin)

    return {
        "file": document.file_path.name,
        "pages": document.page_count,
        "total_words": len(all_words),
        "unique_words": len(counter),
        "top_words": counter.most_common(30),
        "detected_type": detected_type,
        "confidence": confidence,
        "risk": risk,
        "signals": {
            "RD": rd_matches,
            "PUERTO_RICO": pr_matches,
        },
    }
