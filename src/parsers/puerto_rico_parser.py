from __future__ import annotations
from typing import List
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import (
    BaseParser,
    ParserError,
    extract_text_lines,
    parse_weight_from_tokens,
    clean_text,
    normalize_token,
)


class PuertoRicoManifestParser(BaseParser):
    """Parser for PUERTO_RICO manifests.

    This implementation extracts a conservative header record (similar to RD
    parser) and captures weights/hazmat indicators. It can be extended to
    parse detailed table rows later.
    """

    manifest_type = ManifestType.PUERTO_RICO

    def __init__(self, source_file: Path | None = None):
        super().__init__(source_file=source_file)

    def _extract_header(self, lines: List[str]) -> dict:
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

        # patterns
        ship_patterns = ("1.- NAME OF SHIP", "NAME OF SHIP")
        voyage_patterns = ("VOYAGE NUMBER", "VOYAGE")
        loading_patterns = ("5A - LOADING PORT", "LOADING PORT")
        discharge_patterns = ("5B - DISCHARGE PORT", "DISCHARGE PORT")

        # ship
        for i, line in enumerate(lines[:10]):
            if any(p in normalize_token(line) for p in ship_patterns):
                # take following line if exists
                if i + 1 < len(lines):
                    header["ship_name"] = clean_text(lines[i + 1])
                else:
                    header["ship_name"] = clean_text(line)
                break

        # voyage
        for i, line in enumerate(lines[:12]):
            if any(p in normalize_token(line) for p in voyage_patterns):
                header["voyage"] = clean_text(line)
                if i + 1 < len(lines):
                    # try extract brief token
                    header["voyage"] = clean_text(lines[i + 1])
                break

        # ports
        for i, line in enumerate(lines[:20]):
            norm = normalize_token(line)
            if any(p in norm for p in loading_patterns):
                header["loading_port"] = clean_text(line)
                if i + 1 < len(lines):
                    header["loading_port"] = clean_text(lines[i + 1])
            if any(p in norm for p in discharge_patterns):
                header["discharge_port"] = clean_text(line)
                if i + 1 < len(lines):
                    header["discharge_port"] = clean_text(lines[i + 1])

        # weights
        tokens = []
        for l in lines[:40]:
            tokens.extend(clean_text(l).split())
        kg, lbs, matches = parse_weight_from_tokens(tokens)
        header["weight_kg"] = kg
        header["weight_lbs"] = lbs

        # hazmat and customs
        for l in lines[:40]:
            if "HAZARD" in normalize_token(l) or "HAZARDOUS" in l.upper():
                header["has_hazardous"] = True
            if "AES ITN" in l.upper() or "NO EEI" in l.upper() or "SED NOT REQUIRED" in l.upper():
                header["customs_reference"] = clean_text(l)

        return header

    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        try:
            header_lines = extract_text_lines(document, max_pages=3)
            header = self._extract_header(header_lines)

            all_lines = extract_text_lines(document, max_pages=None)
            import re
            records: List[ManifestRecord] = []
            rec_counter = 0
            for i, line in enumerate(all_lines):
                m = re.search(r"(PYRR-\d+)", line, re.IGNORECASE)
                if not m:
                    continue
                bl = m.group(1).upper()
                rec_counter += 1
                context = line
                if i + 1 < len(all_lines):
                    context += " " + all_lines[i + 1]
                if i + 2 < len(all_lines):
                    context += " " + all_lines[i + 2]

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
                )
                records.append(record)

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
            raise ParserError(f"Error parsing PUERTO_RICO manifest: {exc}")
