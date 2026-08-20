from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Tuple, Iterable
from pathlib import Path
import re

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument


class ParserError(Exception):
    pass


class BaseParser(ABC):
    """Abstract base class for manifest parsers.

    Parsers accept a PDFDocument (from core.pdf_reader.read_pdf) and must
    return a list of ManifestRecord instances.

    This base class exposes common utilities for text normalization,
    numeric parsing and simple spatial helpers that operate on the
    PDFDocument.pages / PDFWord structures returned by core.pdf_reader.
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


# ----------------------- Utilities -----------------------

def clean_text(value: str | None) -> str:
    """Normalize whitespace and unicode, return uppercased string.

    Safe to call with None.
    """
    if not value:
        return ""
    s = str(value)
    s = s.replace("\u00A0", " ")  # NBSP
    s = re.sub(r"[\t\r\n]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_optional_value(value: str | None) -> str | None:
    """Return None for placeholders used by PDFs to represent empty fields."""
    cleaned = clean_text(value)
    if not cleaned or cleaned in {"-", "—", "–", "N/A", "N/D"}:
        return None
    return cleaned


def normalize_token(value: str | None) -> str:
    """Uppercase, remove surrounding punctuation, normalize accents.

    Used for robust matching of header tokens (e.g., 'Número de recibo').
    """
    if not value:
        return ""
    s = clean_text(value).upper()
    # Replace common punctuation with spaces and collapse
    s = re.sub(r"[\u2013\u2014\u2012\-–—/\\()\[\]:;,]+", " ", s)
    s = re.sub(r"[^A-Z0-9ÁÉÍÓÚÜÑ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(re.sub(r"[^0-9-]", "", str(value)))
    except Exception:
        return None


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        s = str(value).strip()
        # Accept formats like 1,234.56 or 1.234,56 or plain 1234
        # If both dot and comma present, assume comma is thousands sep when dot follows thousands
        if "," in s and "." in s:
            if s.rfind(',') > s.rfind('.'):
                # German style 1.234,56 -> remove dots, replace comma
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif "," in s:
            # ambiguous: prefer comma as decimal if no dots present and there are 1-2 decimals
            parts = s.split(',')
            if len(parts[-1]) in (1, 2):
                s = s.replace(',', '.')
            else:
                s = s.replace(',', '')
        s = re.sub(r"[^0-9.\-]", "", s)
        return float(s)
    except Exception:
        return None


def parse_weight_from_tokens(tokens: Iterable[str]) -> Tuple[float | None, float | None, list[Tuple[str, str]]]:
    """Scan an iterable of tokens (strings) and extract weight pairs.

    Returns (kg, lbs, matches) where matches is list of (token_before, unit).
    If both are present returns the first observed pair.
    """
    kg = None
    lbs = None
    matches: list[Tuple[str, str]] = []

    token_list = list(tokens)
    for i, tok in enumerate(token_list):
        t = normalize_token(tok)
        # find numeric token preceding unit tokens
        if t in ("KG", "KGS"):
            # try prev token for number
            prev = token_list[i - 1] if i > 0 else ""
            val = _to_float(prev)
            if val is not None:
                kg = val
                matches.append((prev, "KG"))
        if t in ("LBS", "LB"):
            prev = token_list[i - 1] if i > 0 else ""
            val = _to_float(prev)
            if val is not None:
                lbs = val
                matches.append((prev, "LBS"))
    return kg, lbs, matches


def words_in_rect(page, x0: float, y0: float, x1: float, y1: float) -> List[object]:
    """Return words whose bounding boxes intersect the given rectangle."""
    hits: List[object] = []
    for w in getattr(page, "words", []):
        if w.x1 >= x0 and w.x0 <= x1 and w.y1 >= y0 and w.y0 <= y1:
            hits.append(w)
    return sorted(hits, key=lambda w: (w.y0, w.x0))


def rect_text(page, x0: float, y0: float, x1: float, y1: float) -> str:
    """Extract clean text from a spatial rectangle without using page.extract_text()."""
    content = " ".join(clean_text(w.text) for w in words_in_rect(page, x0, y0, x1, y1) if clean_text(w.text))
    return clean_text(content)


def group_words_by_line(page, y_tolerance: float = 3.0) -> List[Tuple[float, List[str]]]:
    """Group PDFPage.words by approximate Y coordinate to reconstruct lines.

    Returns list of tuples (y0, [word_texts]) sorted top->bottom.
    y_tolerance in points (approx pixels) controls grouping sensitivity.
    """
    lines: dict[float, list[str]] = {}
    for w in page.words:
        y = round(w.y0 / y_tolerance) * y_tolerance
        lines.setdefault(y, []).append((w.x0, w.text))

    # sort words in each line by x position
    result: list[Tuple[float, List[str]]] = []
    for y in sorted(lines.keys()):
        row = [t for _, t in sorted(lines[y], key=lambda it: it[0])]
        result.append((y, row))
    return result


def extract_text_lines(document: PDFDocument, max_pages: int | None = 3) -> List[str]:
    """Return textual lines for the first max_pages pages using spatial grouping."""
    lines: List[str] = []
    pages = document.pages if max_pages is None else document.pages[:max_pages]
    for page in pages:
        grouped = group_words_by_line(page)
        for _, row in grouped:
            txt = " ".join(clean_text(t) for t in row if clean_text(t))
            if txt:
                lines.append(txt)
    return lines


def extract_text_lines_with_page(document: PDFDocument, max_pages: int | None = None) -> List[tuple]:
    """Return list of tuples (page_index, y, text) grouped spatially across pages.

    page_index is 1-based.
    """
    results: List[tuple] = []
    pages = document.pages if max_pages is None else document.pages[:max_pages]
    for page in pages:
        grouped = group_words_by_line(page)
        for y, row in grouped:
            txt = " ".join(clean_text(t) for t in row if clean_text(t))
            if txt:
                results.append((page.page_number, y, txt))
    return results


def find_first_matching_line(lines: List[str], patterns: Iterable[str]) -> Tuple[int, str] | Tuple[None, None]:
    """Return (idx, line) of first line containing any normalized pattern, else (None, None)."""
    norms = [normalize_token(p) for p in patterns]
    for i, line in enumerate(lines):
        norm_line = normalize_token(line)
        for pat in norms:
            if pat in norm_line:
                return i, line
    return None, None


def extract_value_after_label(line: str | None, labels: Iterable[str]) -> str | None:
    """Return the value that appears after the label, stripping the label itself.

    Examples:
      "LOADING PORT SAN JUAN (SJU)" with labels=("LOADING PORT",) -> "SAN JUAN (SJU)"
      "VOYAGE AU034S" with labels=("VOYAGE", "VOYAGE NUMBER") -> "AU034S"
    """
    if not line:
        return None
    norm_line = normalize_token(line)
    for label in labels:
        norm_label = normalize_token(label)
        if not norm_label or norm_label not in norm_line:
            continue
        after = line.split(label, 1)[0] if False else None
        # Split on a stable, normalized form to preserve the original content after the label.
        for marker in (label, label.upper(), label.lower()):
            if marker in line:
                after = line.split(marker, 1)[1].strip()
                if after:
                    return clean_text(after)
        after = line.split(label, 1)[1].strip() if label in line else ""
        if after:
            return clean_text(after)
    return clean_text(line)


def strip_party_label(value: str | None, labels: Iterable[str]) -> str:
    """Remove leading party labels like SH, SHIPPER, CO, CONSIGNEE, NO, NOTIFY."""
    text = clean_text(value or "")
    if not text:
        return ""
    for label in labels:
        norm_label = normalize_token(label)
        if not norm_label:
            continue
        if text.upper().startswith(norm_label):
            text = text[len(label):].lstrip(" -:;/")
            break
    return clean_text(text)


def find_party_columns(document: PDFDocument, max_pages: int = 3, x_tol: float = 20.0) -> dict:
    """Detect columns that likely contain SH / CO / NO blocks using top pages.

    Returns mapping like {'SH': x_center, 'CO': x_center, 'NO': x_center} (values in page points).
    """
    candidates: dict[str, list[float]] = {"SH": [], "CO": [], "NO": []}
    tokens = {"SH": ("SH", "SHIPPER"), "CO": ("CO", "CONSIGNEE"), "NO": ("NO", "NOTIFY")}
    pages = document.pages[:max_pages]
    for page in pages:
        for w in page.words:
            tok = normalize_token(w.text)
            for key, variants in tokens.items():
                if tok in {normalize_token(v) for v in variants}:
                    candidates[key].append(w.x0)
    # cluster by simple average per key
    centers: dict[str, float] = {}
    for key, xs in candidates.items():
        if not xs:
            continue
        # average as center
        centers[key] = sum(xs) / len(xs)
    return centers


def get_column_text(page, x_center: float, x_tol: float = 20.0) -> List[str]:
    """Extract text lines from a page that fall within x_center +/- x_tol.

    Returns list of strings sorted top->bottom.
    """
    lines: dict[float, list[tuple]] = {}
    for w in page.words:
        if abs(w.x0 - x_center) <= x_tol:
            y = round(w.y0)
            lines.setdefault(y, []).append((w.x0, w.text))
    result: List[str] = []
    for y in sorted(lines.keys()):
        row = [t for _, t in sorted(lines[y], key=lambda it: it[0])]
        txt = " ".join(clean_text(t) for t in row if clean_text(t))
        if txt:
            result.append(txt)
    return result


def parse_parties_spatial(document: PDFDocument, max_pages: int = 3, x_tol: float = 24.0) -> tuple[str, str, str]:
    """Return a (shipper, consignee, notify) triple using column detection.

    Algorithm:
    1. Find approximate x-centers for SH/CO/NO by scanning top pages for header tokens.
    2. For each detected center, extract column text across the first page and join.
    3. Strip leading SH/CO/NO identifiers and return only the party value.

    This is conservative but more robust than plain text search.
    """
    centers = find_party_columns(document, max_pages=max_pages, x_tol=x_tol)
    shipper = consignee = notify = ""
    # use first page as canonical location for parties
    if not document.pages:
        return shipper, consignee, notify
    page = document.pages[0]
    if "SH" in centers:
        ship_lines = get_column_text(page, centers["SH"], x_tol=x_tol)
        shipper = strip_party_label(" ".join(ship_lines), ("SH", "SHIPPER"))
    if "CO" in centers:
        co_lines = get_column_text(page, centers["CO"], x_tol=x_tol)
        consignee = strip_party_label(" ".join(co_lines), ("CO", "CONSIGNEE"))
    if "NO" in centers:
        no_lines = get_column_text(page, centers["NO"], x_tol=x_tol)
        notify = strip_party_label(" ".join(no_lines), ("NO", "NOTIFY"))
    return shipper, consignee, notify


def parse_party_band(page, y0: float, y1: float) -> tuple[str, str, str]:
    """Extract SH/CO/NO blocks from one cargo row using the left column."""
    words = [w for w in getattr(page, "words", []) if 0 <= w.x0 < 175 and y0 <= w.y0 < y1]
    words.sort(key=lambda w: (w.y0, w.x0))
    sections: dict[str, list[str]] = {"SH": [], "CO": [], "NO": []}
    current: str | None = None
    for word in words:
        token = normalize_token(word.text)
        if token in ("SH", "CO", "NO", "NF") and word.x0 < 20:
            current = "NO" if token == "NF" else token
            continue
        if current and clean_text(word.text):
            value = clean_text(word.text)
            if not re.fullmatch(r"PYRR-\d{4,7}", value.upper()):
                sections[current].append(value)
    return tuple(clean_text(" ".join(sections[key])) for key in ("SH", "CO", "NO"))


def parse_equipment_band(page, y0: float, y1: float) -> tuple[str | None, str | None, str | None, str | None, str | None, bool]:
    """Classify the CN/MN/SN area of one cargo band.

    Returns equipment id, equipment type, marks, seal, AES ITN, and hazardous status. Words are grouped by
    their visual line so split IDs such as ``PRRU 403684-0`` remain intact.
    """
    rows: dict[int, list[object]] = {}
    for word in getattr(page, "words", []):
        if 255 <= word.x0 < 375 and y0 <= word.y0 < y1:
            rows.setdefault(round(word.y0), []).append(word)

    lines = [clean_text(" ".join(w.text for w in sorted(row, key=lambda item: item.x0)))
             for _, row in sorted(rows.items())]
    lines = [line for line in lines if line]
    equipment_id = None
    equipment_type = None
    marks = None
    seal = None
    aes_itn = None
    has_hazardous = False
    seal_values: list[str] = []
    mark_values: list[str] = []

    for index, line in enumerate(lines):
        upper = line.upper()
        id_match = re.search(r"\b([A-Z]{4}\s*\d{4,7}(?:-\d)?|[A-Z0-9]{17})\b", upper)
        if id_match and equipment_id is None:
            equipment_id = id_match.group(1).replace(" ", "")
            continue
        type_match = re.search(r"\b(\d{2}'\s*[A-Z]+|VEHICLE|TANK|PALLET)\b", upper)
        if type_match and equipment_type is None:
            equipment_type = type_match.group(1)
            continue
        if "AES" in upper or "ITN" in upper:
            code_match = re.search(r"\bX[A-Z0-9]+\b", upper)
            if code_match:
                aes_itn = code_match.group(0)
            elif index + 1 < len(lines):
                next_code = re.search(r"\bX[A-Z0-9]+\b", lines[index + 1].upper())
                if next_code:
                    aes_itn = next_code.group(0)
            continue
        if upper.startswith("NO EEI") or upper.startswith("REFERENCE SED") or upper.startswith("SED NOT"):
            continue
        if "HAZARDOUS" in upper or "\uf071" in upper:
            has_hazardous = True
            continue
        if upper.startswith("X"):
            continue
        if upper == "N/A" or re.search(r"[A-Z0-9]{4,}[/-][A-Z0-9]+$", upper) or re.fullmatch(r"[A-Z0-9]{4,}", upper):
            seal_values.append(line)
            continue
        mark_values.append(line)

    if mark_values:
        marks = clean_text(" | ".join(mark_values))
    if seal_values:
        seal = clean_text(" | ".join(seal_values))
    return equipment_id, equipment_type, marks, seal, aes_itn, has_hazardous

# Backwards-compatible small helpers

def parse_int(value: str | None) -> int | None:
    return _to_int(value)


def parse_float(value: str | None) -> float | None:
    return _to_float(value)
