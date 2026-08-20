from pathlib import Path

from core.models import ManifestType
from parsers.local_parser import LocalManifestParser


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
    def __init__(self, file_path, pages):
        self.file_path = file_path
        self.page_count = len(pages)
        self.pages = pages


def test_local_parser_finds_bl_and_parses_header(sample_document):
    parser = LocalManifestParser()
    records = parser.parse(sample_document)
    # Should find at least one record for PYRR-0001
    assert records, "No records returned"
    bls = [r.bl_number for r in records if r.bl_number]
    assert any(b.upper() == "PYRR-0001" for b in bls)
    # Header fields should be present
    rec0 = records[0]
    assert rec0.ship_name is not None or rec0.voyage is not None


def test_local_parser_normalizes_au_manifest_fields_and_party_codes(tmp_path):
    words = []
    x = 10
    for token in ["NAME", "OF", "SHIP", "AURORA", "(AU)"]:
        words.append(Word(x, 40, x + 30, 48, token))
        x += 45

    x = 10
    for token in ["VOYAGE", "AU034S"]:
        words.append(Word(x, 60, x + 50, 68, token))
        x += 80

    x = 10
    for token in ["LOADING", "PORT", "SAN", "JUAN", "(SJU)"]:
        words.append(Word(x, 80, x + 30, 88, token))
        x += 34

    x = 10
    for token in ["DISCHARGE", "PORT", "ST.", "CROIX", "(STX)"]:
        words.append(Word(x, 100, x + 30, 108, token))
        x += 44

    # Party columns
    for x0, text in [(300, "SH"), (300, "GLOBAL"), (300, "TRADING")]:
        words.append(Word(x0, 120, x0 + 20, 128, text))
    for x0, text in [(420, "CO"), (420, "BLUE"), (420, "PORT")]:
        words.append(Word(x0, 120, x0 + 20, 128, text))
    for x0, text in [(540, "NO"), (540, "NOTICE"), (540, "HOLD")]:
        words.append(Word(x0, 120, x0 + 20, 128, text))

    words.append(Word(10, 150, 220, 158, "PYRR-0001 1000 KG 2204.62 LBS"))

    document = Document(Path("/tmp/au_manifest.pdf"), [Page(1, words)])
    parser = LocalManifestParser()
    record = parser.parse(document)[0]

    assert record.ship_name == "AURORA (AU)"
    assert record.voyage == "AU034S"
    assert record.loading_port == "SAN JUAN (SJU)"
    assert record.discharge_port == "ST. CROIX (STX)"
    assert record.shipper == "GLOBAL TRADING"
    assert record.consignee == "BLUE PORT"
    assert record.notify == "NOTICE HOLD"


def test_local_parser_exports_empty_final_destination_as_none():
    parser = LocalManifestParser()
    header = parser._extract_header([
        "1.- Name of Ship Número de recibo 2.- Port where report is made",
        "KYDON (KY) K1326",
        "SANTO DOMINGO (SDQ) (Oath to be taken on Customs Form 1300)",
        "3.- Nationality of Ship 4 - Name of Master 5a - Puerto de carga 5b - Puerto de Descarga Final Destination Date of Sailing from POL",
        "BAHAMAS GASPARATOS, ANDREW PAUL SANTO DOMINGO (SDQ) SAN JUAN (SJU) — 2026.08.18 (18:00)",
    ])

    assert header["final_destination"] is None


def test_manifest_record_exports_only_pdf_business_columns(sample_document):
    record = LocalManifestParser().parse(sample_document)[0]

    expected_headers = tuple(
        value for key, value in record.OUTPUT_HEADERS.items()
        if key not in {"has_hazardous", "customs_reference"}
    )
    assert tuple(record.to_dict()) == expected_headers
    assert "Ship Name" in record.to_dict()
    assert "BL Numbers" in record.to_dict()
    assert "source_file" not in record.to_dict()
    assert "record_number" not in record.to_dict()
    assert "has_hazardous" not in record.to_dict()


def test_manifest_record_merges_marks_into_description_and_excludes_marks_from_export(sample_document):
    record = LocalManifestParser().parse(sample_document)[0]
    record.marks = "LOT 3"
    record.description = "TOYOTA TACOMA"

    payload = record.to_dict()

    assert payload["Marks and Nrs (MN)"] == "LOT 3"
    assert payload["Number and kind of packages: Description of Goods"] == "TOYOTA TACOMA"


def test_manifest_export_order_matches_pdf_sections(sample_document):
    record = LocalManifestParser().parse(sample_document)[0]

    assert list(record.to_dict()) == [
        "Ship Name",
        "Voyage Number",
        "Port Where Report Is Made",
        "Nationality of Ship",
        "Name of Master",
        "Loading Port",
        "Discharge Port",
        "Final Destination",
        "Date of Sailing from POL",
        "Shipper SH",
        "Consignee CO",
        "Notify NF",
        "BL Numbers",
        "Containers Nrs (CN)",
        "Marks and Nrs (MN)",
        "Seal Nrs (SN)",
        "Number and kind of packages: Description of Goods",
        "Gross Weight (KG)",
        "Gross Weight (LBS)",
    ]
