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
    loading_port: Optional[str] = None
    discharge_port: Optional[str] = None

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

    def to_dict(self) -> dict:
        """Return a serializable dict representation of the record."""
        return {
            "source_file": str(self.source_file),
            "manifest_type": self.manifest_type.value if isinstance(self.manifest_type, ManifestType) else str(self.manifest_type),
            "page": self.page,
            "record_number": self.record_number,
            "ship_name": self.ship_name,
            "voyage": self.voyage,
            "loading_port": self.loading_port,
            "discharge_port": self.discharge_port,
            "shipper": self.shipper,
            "consignee": self.consignee,
            "notify": self.notify,
            "bl_number": self.bl_number,
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type,
            "seal": self.seal,
            "marks": self.marks,
            "quantity": self.quantity,
            "unit": self.unit,
            "description": self.description,
            "weight_kg": self.weight_kg,
            "weight_lbs": self.weight_lbs,
            "customs_reference": self.customs_reference,
            "has_hazardous": self.has_hazardous,
        }


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
