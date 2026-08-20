from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ManifestType(str, Enum):
    RD = "RD"
    PUERTO_RICO = "PUERTO_RICO"
    UNKNOWN = "UNKNOWN"
    # Backward compatibility alias for older code/tests.
    LOCAL = "RD"


@dataclass
class ManifestRecord:
    """Normalized manifest record produced by parsers.

    Parsers should populate what they can and leave other fields None when
    absent. Field names are chosen to be descriptive and consistent across
    formats (RD / Puerto Rico).
    """
    source_file: Path
    manifest_type: ManifestType
    page: int
    record_number: int

    # Core identification and routing
    ship_name: Optional[str] = None
    voyage: Optional[str] = None
    report_port: Optional[str] = None
    nationality: Optional[str] = None
    name_of_master: Optional[str] = None
    loading_port: Optional[str] = None
    discharge_port: Optional[str] = None
    final_destination: Optional[str] = None
    date_of_sailing: Optional[str] = None

    # Parties
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    notify: Optional[str] = None

    # References / equipment
    bl_number: Optional[str] = None
    equipment_id: Optional[str] = None
    equipment_type: Optional[str] = None
    seal: Optional[str] = None
    marks: Optional[str] = None

    # Cargo details
    quantity: Optional[float] = None
    unit: Optional[str] = None
    description: Optional[str] = None

    # Weights
    weight_kg: Optional[float] = None
    weight_lbs: Optional[float] = None

    # Extra fields
    customs_reference: Optional[str] = None
    has_hazardous: Optional[bool] = None

    # Only these fields are exported. The parser metadata above remains
    # internal and is intentionally excluded from CSV, JSON and Excel.
    OUTPUT_COLUMNS = (
        "ship_name",
        "voyage",
        "report_port",
        "nationality",
        "name_of_master",
        "loading_port",
        "discharge_port",
        "final_destination",
        "date_of_sailing",
        "shipper",
        "consignee",
        "notify",
        "bl_number",
        "equipment_id",
        "marks",
        "seal",
        "customs_reference",
        "has_hazardous",
        "description",
        "weight_kg",
        "weight_lbs",
    )

    OUTPUT_HEADERS = {
        "ship_name": "Ship Name",
        "voyage": "Voyage Number",
        "report_port": "Port Where Report Is Made",
        "nationality": "Nationality of Ship",
        "name_of_master": "Name of Master",
        "loading_port": "Loading Port",
        "discharge_port": "Discharge Port",
        "final_destination": "Final Destination",
        "date_of_sailing": "Date of Sailing from POL",
        "shipper": "Shipper SH",
        "consignee": "Consignee CO",
        "notify": "Notify NF",
        "bl_number": "BL Numbers",
        "equipment_id": "Containers Nrs (CN)",
        "marks": "Marks and Nrs (MN)",
        "seal": "Seal Nrs (SN)",
        "customs_reference": "AES ITN",
        "has_hazardous": "Hazardous Cargo",
        "description": "Number and kind of packages: Description of Goods",
        "weight_kg": "Gross Weight (KG)",
        "weight_lbs": "Gross Weight (LBS)",
    }

    def to_dict(self) -> dict:
        """Return the fixed business schema used by every exporter.

        Keep the PDF's equipment, marks, and seal fields as separate export columns.
        """
        data = {
            self.OUTPUT_HEADERS[column]: getattr(self, column)
            for column in self.OUTPUT_COLUMNS
        }
        if self.manifest_type != ManifestType.PUERTO_RICO:
            data.pop(self.OUTPUT_HEADERS["has_hazardous"], None)
            data.pop(self.OUTPUT_HEADERS["customs_reference"], None)
        hazardous_key = self.OUTPUT_HEADERS["has_hazardous"]
        if hazardous_key in data and data[hazardous_key] is False:
            data[hazardous_key] = None

        container_key = self.OUTPUT_HEADERS["equipment_id"]
        container_value = str(data.get(container_key) or "").strip()
        equipment_value = str(self.equipment_type or "").strip()
        if equipment_value and equipment_value not in container_value:
            data[container_key] = " ".join(filter(None, (container_value, equipment_value)))

        return data


@dataclass
class ManifestAnalysis:
    file: str
    pages: int
    total_words: int
    unique_words: int
    top_words: list
    detected_type: Optional[ManifestType] = None
    confidence: Optional[float] = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list
    warnings: list
