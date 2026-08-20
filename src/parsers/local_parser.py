from __future__ import annotations
from typing import List, Tuple
from pathlib import Path

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import (
    BaseParser,
    ParserError,
    extract_text_lines,
    extract_value_after_label,
    find_first_matching_line,
    parse_weight_from_tokens,
    normalize_token,
    clean_text,
    clean_optional_value,
    parse_parties_spatial,
    parse_party_band,
    parse_equipment_band,
)
import re


def _extract_equipment_and_marks_rd(text: str) -> tuple[list[str], str | None, str | None, float | None, str | None, str | None]:
    """Heuristic extraction for RD lines. Returns (equipment_ids, seal, marks, quantity, unit, description).

    equipment_ids: list of container-like ids (may be empty)
    seal: single seal string when found
    marks: marks text when found
    quantity: numeric package count
    unit: unit string (PKGS, CTNS, etc.)
    description: cleaned short description
    """
    t = text.upper()
    equipment_ids: list[str] = []
    seal: str | None = None
    marks: str | None = None
    quantity: float | None = None
    unit: str | None = None
    description: str | None = None

    # Find multiple ISO-style container ids
    for m in re.finditer(r"\b([A-Z]{4}\d{7})\b", t):
        equipment_ids.append(m.group(1))

    # seals: common patterns like SEAL NO: 1234 or the final token in an equipment row
    m = re.search(r"SEAL(?:S| NO| NO\.)?[:\s]*([A-Z0-9\-]+)", t)
    if m:
        seal = m.group(1)

    # marks
    m = re.search(r"MARKS(?: AND NRS| AND NOS| AND NR)?[:\s]*([A-Z0-9 \-\.,/]+)", t)
    if m:
        marks = m.group(1).strip()

    # package quantity and unit
    for u in ("PACKAGES", "PACKAGE", "PACKS", "PACK", "UNITS", "UNIT", "BOXES", "BOX", "CONTAINER", "CONTAINERS", "VEHICLE", "PKGS", "PKG", "CTNS", "CTN", "BAGS", "BAG", "PCS", "PIECES", "TONS", "TON", "KGS", "KG"):
        m = re.search(rf"(\d+(?:[\.,]\d+)?)\s*{u}\b", t)
        if m:
            try:
                quantity = float(m.group(1).replace(',', ''))
                unit = u
                break
            except Exception:
                pass

    description = clean_text(text)[:240]

    return equipment_ids, seal, marks, quantity, unit, description



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
            "report_port": None,
            "nationality": None,
            "name_of_master": None,
            "loading_port": None,
            "discharge_port": None,
            "final_destination": None,
            "date_of_sailing": None,
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
        report_patterns = ("PORT WHERE REPORT IS MADE", "PUERTO DONDE SE HACE EL REPORTE")
        nationality_patterns = ("NATIONALITY OF SHIP", "NACIONALIDAD DEL BUQUE")
        master_patterns = ("NAME OF MASTER", "NOMBRE DEL CAPITAN", "NAME OF CAPTAIN")

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
            for pat in ship_patterns:
                if normalize_token(pat) in normalize_token(norm):
                    ship = extract_value_after_label(norm, (pat,))
                    if ship:
                        header["ship_name"] = _extract_ship_from_text(ship)
                        break
            if not header["ship_name"] and idx + 1 < len(lines):
                header["ship_name"] = _extract_ship_from_text(lines[idx + 1])

        # voyage
        idx, line = find_first_matching_line(lines, voyage_patterns)
        if idx is not None:
            for pat in voyage_patterns:
                if normalize_token(pat) in normalize_token(line):
                    voyage = extract_value_after_label(line, (pat,))
                    if voyage:
                        header["voyage"] = clean_text(voyage)
                        break
            if not header["voyage"] and idx + 1 < len(lines):
                header["voyage"] = clean_text(lines[idx + 1])

        # loading / discharge
        idx, _ = find_first_matching_line(lines, loading_patterns)
        if idx is not None:
            for pat in loading_patterns:
                if normalize_token(pat) in normalize_token(lines[idx]):
                    port = extract_value_after_label(lines[idx], (pat,))
                    if port:
                        header["loading_port"] = port
                        break
            if not header["loading_port"] and idx + 1 < len(lines):
                header["loading_port"] = clean_text(lines[idx + 1])
        idx, _ = find_first_matching_line(lines, discharge_patterns)
        if idx is not None:
            for pat in discharge_patterns:
                if normalize_token(pat) in normalize_token(lines[idx]):
                    port = extract_value_after_label(lines[idx], (pat,))
                    if port:
                        header["discharge_port"] = port
                        break
            if not header["discharge_port"] and idx + 1 < len(lines):
                header["discharge_port"] = clean_text(lines[idx + 1])

        def _read_labeled_value(patterns):
            idx, line = find_first_matching_line(lines, patterns)
            if idx is None:
                return None
            value = extract_value_after_label(line, patterns)
            return value or (clean_text(lines[idx + 1]) if idx + 1 < len(lines) else None)

        header["report_port"] = _read_labeled_value(report_patterns)
        header["nationality"] = _read_labeled_value(nationality_patterns)
        header["name_of_master"] = _read_labeled_value(master_patterns)

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

        # final destination and date of sailing and name of master (if present)
        for l in lines[:60]:
            norm = normalize_token(l)
            if "FINAL DESTINATION" in norm or "DESTINO FINAL" in norm:
                # value may follow on same or next line
                parts = l.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    header["final_destination"] = clean_optional_value(parts[1])
                else:
                    # try next line
                    idx = lines.index(l)
                    if idx + 1 < len(lines):
                        header["final_destination"] = clean_optional_value(lines[idx + 1])
            if "DATE OF SAILING" in norm or "DATE OF SAILING FROM POL" in norm or "FECHA DE SALIDA" in norm:
                parts = l.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    header["date_of_sailing"] = clean_text(parts[1])
                else:
                    idx = lines.index(l)
                    if idx + 1 < len(lines):
                        header["date_of_sailing"] = clean_text(lines[idx + 1])
            if "NAME OF MASTER" in norm or "NOMBRE DEL CAPITAN" in norm or "NAME OF CAPTAIN" in norm:
                parts = l.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    header["name_of_master"] = clean_text(parts[1])
                else:
                    idx = lines.index(l)
                    if idx + 1 < len(lines):
                        header["name_of_master"] = clean_text(lines[idx + 1])

        # The PDF places the header labels on one row and their values on the
        # next row, so label-based extraction can otherwise capture all labels.
        label_index = next((i for i, line in enumerate(lines[:10]) if "NAME OF SHIP" in normalize_token(line)), None)
        if label_index is not None and len(lines) > label_index + 4:
            ship_line = lines[label_index + 1]
            ship_match = re.search(r"(.+?\([A-Z]{2,4}\))\s+([A-Z0-9]+)\s+(?:made|$)", ship_line, re.I)
            if ship_match:
                header["ship_name"] = clean_text(ship_match.group(1))
                header["voyage"] = clean_text(ship_match.group(2))
            header["report_port"] = clean_text(lines[label_index + 2].split("(Oath", 1)[0])

            detail = lines[label_index + 4]
            if re.search(r"(?:^|\s)[—–-](?:\s|$)", detail):
                header["final_destination"] = None
            port_matches = re.findall(r"([A-Z][A-Z .'-]{2,30})\s+\(([A-Z0-9-]{2,4})\)", detail)
            ports = [" ".join(raw.split()[-2:]) + f" ({code})" for raw, code in port_matches]
            if len(ports) >= 2:
                header["loading_port"] = clean_text(ports[-2])
                header["discharge_port"] = clean_text(ports[-1])
            date_match = re.search(r"\d{4}\.\d{2}\.\d{2}\s+\([^)]*\)", detail)
            if date_match:
                header["date_of_sailing"] = date_match.group(0)
            if ports:
                prefix = detail[:detail.find(ports[0].split(" (")[0])].strip()
                prefix = prefix.rstrip("—-").strip()
                header["nationality"] = prefix.split()[0] if prefix else None
                master = prefix[len(header["nationality"]):].strip() if header["nationality"] else ""
                header["name_of_master"] = master or None

        return header

    def parse(self, document: PDFDocument) -> List[ManifestRecord]:
        try:
            header_lines = extract_text_lines(document, max_pages=3)
            header = self._extract_header(header_lines)
            shipper_text, consignee_text, notify_text = parse_parties_spatial(document)

            records: List[ManifestRecord] = []
            rec_counter = 0

            for page in document.pages:
                bl_candidates = []
                for word in getattr(page, "words", []):
                    text = clean_text(word.text).upper()
                    match = re.search(r"PYRR-\d{4,7}", text)
                    if match:
                        bl_candidates.append((word, match.group(0)))

                for index, (bl_word, bl_value) in enumerate(bl_candidates):
                    rec_counter += 1
                    y0 = bl_word.y0 - 2
                    next_y = bl_candidates[index + 1][0].y0 if index + 1 < len(bl_candidates) else page.height
                    y1 = (bl_word.y0 + next_y) / 2
                    equipment_text = clean_text(" ".join(w.text for w in sorted(page.words, key=lambda item: (item.y0, item.x0)) if 255 <= w.x0 < 375 and y0 <= w.y0 < y1))
                    cargo_text = clean_text(" ".join(w.text for w in sorted(page.words, key=lambda item: (item.y0, item.x0)) if 375 <= w.x0 < 505 and y0 <= w.y0 < y1))
                    weights_text = clean_text(" ".join(w.text for w in sorted(page.words, key=lambda item: (item.y0, item.x0)) if 505 <= w.x0 < 660 and y0 <= w.y0 < y1))
                    shipper_text, consignee_text, notify_text = parse_party_band(page, y0, next_y - 2)
                    spatial_equipment_id, spatial_type, spatial_marks, spatial_seal, spatial_aes_itn, spatial_hazardous = parse_equipment_band(page, y0, y1)
                    if not any((shipper_text, consignee_text, notify_text)):
                        shipper_text, consignee_text, notify_text = parse_parties_spatial(document)

                    equipment_ids, seal_val, marks_val, qty_val, unit_val, desc_val = _extract_equipment_and_marks_rd(
                        " ".join(part for part in [equipment_text, cargo_text] if part)
                    )
                    equipment_match = re.search(r"\b([A-Z]{4}\s*\d{4,7}(?:-\d)?|[A-Z0-9]{17})\b", equipment_text.upper())
                    seal_match = re.search(r"\b([A-Z]{2,}\d{4,})\b", equipment_text.upper())
                    description = cargo_text or desc_val or clean_text(" ".join(part for part in [equipment_text, cargo_text] if part))
                    if marks_val and description:
                        description = f"{description} {marks_val}".strip()

                    kg, lbs, _ = parse_weight_from_tokens(weights_text.split())
                    if kg is None and lbs is None:
                        kg, lbs, _ = parse_weight_from_tokens(clean_text(cargo_text + " " + weights_text).split())

                    record = ManifestRecord(
                        source_file=document.file_path,
                        manifest_type=self.manifest_type,
                        page=page.page_number,
                        record_number=rec_counter,
                        ship_name=header.get("ship_name"),
                        voyage=header.get("voyage"),
                        report_port=header.get("report_port"),
                        nationality=header.get("nationality"),
                        name_of_master=header.get("name_of_master"),
                        loading_port=header.get("loading_port"),
                        discharge_port=header.get("discharge_port"),
                        final_destination=header.get("final_destination"),
                        date_of_sailing=header.get("date_of_sailing"),
                        weight_kg=kg,
                        weight_lbs=lbs,
                        customs_reference=spatial_aes_itn,
                        has_hazardous=spatial_hazardous,
                        bl_number=bl_value.upper(),
                        equipment_id=spatial_equipment_id or (equipment_ids[0] if equipment_ids else None) or (equipment_match.group(1).replace(" ", "") if equipment_match else None),
                        equipment_type=spatial_type or (re.search(r"\b(VEHICLE|\d{2}'\s*[A-Z]+|TANK|PALLET)\b", equipment_text.upper()) or [None, None])[1],
                        seal=spatial_seal or seal_val or (seal_match.group(1) if seal_match else None),
                        marks=spatial_marks or marks_val or None,
                        quantity=qty_val,
                        unit=unit_val,
                        description=description,
                        shipper=shipper_text or None,
                        consignee=consignee_text or None,
                        notify=notify_text or None,
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
                    report_port=header.get("report_port"),
                    nationality=header.get("nationality"),
                    name_of_master=header.get("name_of_master"),
                    loading_port=header.get("loading_port"),
                    discharge_port=header.get("discharge_port"),
                    final_destination=header.get("final_destination"),
                    date_of_sailing=header.get("date_of_sailing"),
                    weight_kg=header.get("weight_kg"),
                    weight_lbs=header.get("weight_lbs"),
                    customs_reference=header.get("customs_reference"),
                    has_hazardous=header.get("has_hazardous"),
                )
                return [rec]

            return records

        except Exception as exc:  # pragma: no cover - conservative fallback
            raise ParserError(f"Error parsing RD manifest: {exc}")
