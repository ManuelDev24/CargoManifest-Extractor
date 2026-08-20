from __future__ import annotations
from typing import List
from pathlib import Path
import re

from core.models import ManifestRecord, ManifestType
from core.pdf_reader import PDFDocument
from parsers.base_parser import (
    BaseParser,
    ParserError,
    extract_text_lines,
    extract_value_after_label,
    parse_weight_from_tokens,
    clean_text,
    normalize_token,
    parse_parties_spatial,
    parse_party_band,
    parse_equipment_band,
)


def _extract_equipment_and_marks(text: str) -> tuple[str | None, str | None, str | None, float | None, str | None, str | None]:
    """Heuristic extraction of equipment id (container), seal, marks, quantity/unit and description from a text blob.

    Returns: (equipment_id, seal, marks, quantity, unit, description)
    All string results are uppercased/preserved as found; quantity is a float when found.
    """
    t = text.upper()
    equipment_id: str | None = None
    seal: str | None = None
    marks: str | None = None
    quantity: float | None = None
    unit: str | None = None
    description: str | None = None

    # ISO containers and 17-character vehicle/chassis identifiers.
    m = re.search(r"\b([A-Z]{4}\d{7}|[A-Z0-9]{17})\b", t)
    if m:
        equipment_id = m.group(1)

    type_match = re.search(r"\b(\d{2}'\s*(?:CONT|FLATBED)|VEHICLE|TANK|PALLET)\b", t)

    # seal patterns
    m = re.search(r"SEAL(?:S| NO| NO\.)?[:\s]*([A-Z0-9\-]+)", t)
    if m:
        seal = m.group(1)

    # marks (take following chunk up to common separators)
    m = re.search(r"MARKS(?: AND NRS| AND NOS| AND NR)?[:\s]*([A-Z0-9 \-\.,/]+)", t)
    if m:
        marks = m.group(1).strip()

    # quantity and unit (common units)
    for u in ("PACKAGES", "PACKAGE", "PACKS", "PACK", "UNITS", "UNIT", "BOXES", "BOX", "CONTAINER", "CONTAINERS", "VEHICLE", "PKGS", "PKG", "CTNS", "CTN", "BAGS", "BAG", "PCS", "PIECES", "TONS", "TON", "KGS", "KG"):
        m = re.search(rf"(\d+(?:[\.,]\d+)?)\s*{u}\b", t)
        if m:
            try:
                quantity = float(m.group(1).replace(',', ''))
                unit = u
                break
            except Exception:
                pass

    # as a last resort try to extract a short descriptive phrase after the BL or after marks
    # take up to 120 chars of the original text as description
    description = clean_text(text)[:240]

    if not seal:
        seal_match = re.search(r"\b([A-Z]{2,}\d{4,}|\d{4,})\b$", t)
        if seal_match and not re.fullmatch(r"\d+(?:\.\d+)?", seal_match.group(1)):
            seal = seal_match.group(1)

    return equipment_id, seal, marks, quantity, unit, description


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

        # patterns
        ship_patterns = ("1.- NAME OF SHIP", "NAME OF SHIP")
        voyage_patterns = ("VOYAGE NUMBER", "VOYAGE")
        loading_patterns = ("5A - LOADING PORT", "LOADING PORT")
        discharge_patterns = ("5B - DISCHARGE PORT", "DISCHARGE PORT")
        report_patterns = ("PORT WHERE REPORT IS MADE",)
        nationality_patterns = ("NATIONALITY OF SHIP",)
        master_patterns = ("NAME OF MASTER", "NAME OF CAPTAIN")

        # ship
        for i, line in enumerate(lines[:10]):
            for pat in ship_patterns:
                if normalize_token(pat) in normalize_token(line):
                    ship = extract_value_after_label(line, (pat,))
                    if ship:
                        header["ship_name"] = ship
                    elif i + 1 < len(lines):
                        header["ship_name"] = clean_text(lines[i + 1])
                    break
            if header["ship_name"]:
                break

        # voyage
        for i, line in enumerate(lines[:12]):
            for pat in voyage_patterns:
                if normalize_token(pat) in normalize_token(line):
                    voyage = extract_value_after_label(line, (pat,))
                    if voyage:
                        header["voyage"] = voyage
                    elif i + 1 < len(lines):
                        header["voyage"] = clean_text(lines[i + 1])
                    break
            if header["voyage"]:
                break

        # ports
        for i, line in enumerate(lines[:20]):
            norm = normalize_token(line)
            for pat in loading_patterns:
                if normalize_token(pat) in norm:
                    port = extract_value_after_label(line, (pat,))
                    header["loading_port"] = port or clean_text(line)
                    if not port and i + 1 < len(lines):
                        header["loading_port"] = clean_text(lines[i + 1])
                    break

            for pat in discharge_patterns:
                if normalize_token(pat) in norm:
                    port = extract_value_after_label(line, (pat,))
                    header["discharge_port"] = port or clean_text(line)
                    if not port and i + 1 < len(lines):
                        header["discharge_port"] = clean_text(lines[i + 1])
                    break

        def _read_labeled_value(patterns):
            for i, line in enumerate(lines[:20]):
                for pat in patterns:
                    if normalize_token(pat) in normalize_token(line):
                        value = extract_value_after_label(line, (pat,))
                        return value or (clean_text(lines[i + 1]) if i + 1 < len(lines) else None)
            return None

        header["report_port"] = _read_labeled_value(report_patterns)
        header["nationality"] = _read_labeled_value(nationality_patterns)
        header["name_of_master"] = _read_labeled_value(master_patterns)

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
            port_matches = re.findall(r"([A-Z][A-Z .'-]{2,30})\s+\(([A-Z0-9-]{2,4})\)", detail)
            ports = [" ".join(raw.split()[-2:]) + f" ({code})" for raw, code in port_matches]
            if len(ports) >= 2:
                header["loading_port"] = clean_text(ports[-2])
                header["discharge_port"] = clean_text(ports[-1])
            date_match = re.search(r"\d{4}\.\d{2}\.\d{2}\s+\([^)]*\)", detail)
            if date_match:
                header["date_of_sailing"] = date_match.group(0)
            if ports:
                prefix = detail[:detail.find(ports[0].split(" (")[0])].strip().rstrip("—-").strip()
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

                    equipment_id, seal_val, marks_val, qty_val, unit_val, desc_val = _extract_equipment_and_marks(
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
                        equipment_id=spatial_equipment_id or equipment_id or (equipment_match.group(1).replace(" ", "") if equipment_match else None),
                        equipment_type=spatial_type or (re.search(r"\b(\d{2}'\s*[A-Z]+|VEHICLE|TANK|PALLET)\b", equipment_text.upper()) or [None, None])[1],
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
            raise ParserError(f"Error parsing PUERTO_RICO manifest: {exc}")
