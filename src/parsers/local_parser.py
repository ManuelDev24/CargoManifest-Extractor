from __future__ import annotations
from typing import List, Tuple
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import (
    BaseParser,
    ParserError,
    extract_text_lines,
    find_first_matching_line,
    parse_weight_from_tokens,
    normalize_token,
    clean_text,
    parse_parties_spatial,
)


class LocalManifestParser(BaseParser):
    """Parser for RD (Dominican) format manifests.

    This implementation focuses on extracting header-level information
    (ship_name, voyage, loading_port, discharge_port, weights and hazmat)
    as a first, conservative pass. Later iterations can split full cargo
    table rows into multiple ManifestRecord entries.
    """

    manifest_type = ManifestType.RD

    def __init__(self, source_file: Path | None = None):
        super().__init__(source_file=source_file)

    def _extract_header(self, lines: List[str]) -> dict:
        """Extract top-level header fields from lines (first pages).

        Returns a dict with keys ship_name, voyage, loading_port,
        discharge_port, weight_kg, weight_lbs, has_hazardous, customs_ref
        """
        header = {
            "ship_name": None,
            "voyage": None,
            "loading_port": None,
            "discharge_port": None,
            "weight_kg": None,
            "weight_lbs": None,
            "has_hazardous": False,
            "customs_reference": None,
        }

        # Patterns to search
        ship_patterns = ("NAME OF SHIP", "NOMBRE DEL BARCO")
        voyage_patterns = ("VOYAGE NUMBER", "VOYAGE", "NUMERO DE RECIBO")
        loading_patterns = ("LOADING PORT", "PUERTO DE CARGA")
        discharge_patterns = ("DISCHARGE PORT", "PUERTO DE DESCARGA")

        # Helper to pick a sensible ship name from a text blob
        def _extract_ship_from_text(text: str) -> str | None:
            import re
            # prefer patterns like NAME (XX)
            m = re.search(r"([A-ZÁÉÍÓÚÑ0-9 .'\-]{3,60}\([A-Z]{1,4}\))", text)
            if m:
                return clean_text(m.group(1))
            # fallback: first token group before double spaces or '  '
            parts = text.split('  ')
            if parts:
                candidate = parts[0].strip()
                if len(candidate) > 2 and any(c.isalpha() for c in candidate):
                    return clean_text(candidate)
            # last fallback: whole text trimmed
            t = clean_text(text)
            return t if t else None

        # Find ship name (usually label followed by value next token/line)
        idx, line = find_first_matching_line(lines, ship_patterns)
        if idx is not None:
            # value often appears on same line after label or on following line
            norm = line  # use original (not fully normalized) to preserve accents/parenthesis
            # attempt to take text after label
            for pat in ship_patterns:
                p = normalize_token(pat)
                if p in normalize_token(norm):
                    # split on the pattern in the normalized line but extract from original
                    try:
                        after = norm.upper().split(p, 1)[1].strip()
                    except Exception:
                        after = ''
                    if after:
                        ship = _extract_ship_from_text(after)
                        if ship:
                            header["ship_name"] = ship
                            break
            if not header["ship_name"] and idx + 1 < len(lines):
                header["ship_name"] = _extract_ship_from_text(lines[idx + 1])

        # voyage
        idx, line = find_first_matching_line(lines, voyage_patterns)
        if idx is not None:
            norm = normalize_token(line)
            for pat in voyage_patterns:
                p = normalize_token(pat)
                if p in norm:
                    after = norm.split(p, 1)[1].strip()
                    if after:
                        header["voyage"] = clean_text(after)
                        break
            if not header["voyage"] and idx + 1 < len(lines):
                header["voyage"] = clean_text(lines[idx + 1])

        # loading / discharge
        idx, line = find_first_matching_line(lines, loading_patterns)
        if idx is not None:
            # value may be later on same or next line
            # take first parenthetical token like (SDQ) or full name
            txt = lines[idx]
            header["loading_port"] = clean_text(txt)
            if idx + 1 < len(lines):
                nxt = lines[idx + 1]
                if '(' in nxt or ')' in nxt:
                    header["loading_port"] = clean_text(nxt)
        idx, line = find_first_matching_line(lines, discharge_patterns)
        if idx is not None:
            header["discharge_port"] = clean_text(lines[idx])
            if idx + 1 < len(lines):
                header["discharge_port"] = clean_text(lines[idx + 1])

        # has hazardous
        for l in lines[:10]:
            if "HAZARD" in normalize_token(l) or "HAS HAZARDOUS" in l.upper():
                header["has_hazardous"] = True
                break

        # weights: scan first few lines tokens
        sample_tokens = []
        for l in lines[:30]:
            for tok in clean_text(l).split():
                sample_tokens.append(tok)
        kg, lbs, matches = parse_weight_from_tokens(sample_tokens)
        header["weight_kg"] = kg
        header["weight_lbs"] = lbs

        # customs reference (AES ITN or similar)
        for l in lines[:40]:
            if "AES ITN" in l.upper() or "ITN" in l.upper():
                header["customs_reference"] = clean_text(l)
                break

        return header

    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        try:
            # extract header from first pages
            header_lines = extract_text_lines(document, max_pages=3)
            header = self._extract_header(header_lines)

            # search all pages for BL occurrences to create one record per BL
            all_lines = extract_text_lines(document, max_pages=None)
            import re
            records: List[ManifestRecord] = []
            rec_counter = 0
            # party extraction (spatial columns)
            shipper_text, consignee_text, notify_text = parse_parties_spatial(document)

            for i, line in enumerate(all_lines):
                m = re.search(r"(PYRR-\d+)", line, re.IGNORECASE)
                if not m:
                    continue
                bl = m.group(1).upper()
                rec_counter += 1

                # gather context tokens (line and next 2 lines)
                context = line
                if i + 1 < len(all_lines):
                    context += " " + all_lines[i + 1]
                if i + 2 < len(all_lines):
                    context += " " + all_lines[i + 2]

                # try extract weights from context
                tokens = [t for t in clean_text(context).split()]
                kg, lbs, matches = parse_weight_from_tokens(tokens)

                record = ManifestRecord(
                    source_file=document.file_path,
                    manifest_type=self.manifest_type,
                    page=1,
                    record_number=rec_counter,
                    ship_name=header.get("ship_name"),
                    voyage=header.get("voyage"),
                    loading_port=header.get("loading_port"),
                    discharge_port=header.get("discharge_port"),
                    weight_kg=kg,
                    weight_lbs=lbs,
                    customs_reference=header.get("customs_reference"),
                    has_hazardous=header.get("has_hazardous"),
                    bl_number=bl,
                    description=clean_text(context),
                    shipper=shipper_text or None,
                    consignee=consignee_text or None,
                    notify=notify_text or None,
                )
                records.append(record)

            # fallback: if no BLs found, return single header record
            if not records:
                rec = ManifestRecord(
                    source_file=document.file_path,
                    manifest_type=self.manifest_type,
                    page=1,
                    record_number=1,
                    ship_name=header.get("ship_name"),
                    voyage=header.get("voyage"),
                    loading_port=header.get("loading_port"),
                    discharge_port=header.get("discharge_port"),
                    weight_kg=header.get("weight_kg"),
                    weight_lbs=header.get("weight_lbs"),
                    customs_reference=header.get("customs_reference"),
                    has_hazardous=header.get("has_hazardous"),
                )
                return [rec]

            return records

        except Exception as exc:  # pragma: no cover - conservative fallback
            raise ParserError(f"Error parsing RD manifest: {exc}")
