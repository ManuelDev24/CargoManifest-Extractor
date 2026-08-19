from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ManifestType(str, Enum):
    LOCAL = "LOCAL"
    PUERTO_RICO = "PUERTO_RICO"
    UNKNOWN = "UNKNOWN"


@dataclass
class ManifestRecord:
    """Normalized manifest record produced by parsers.

    Fields chosen to cover common values across formats. Parsers should
    populate what they can and leave other fields None when absent.
    """
    source_file: Path
    manifest_type: ManifestType
    page: int
    record_number: int

    shipper: Optional[str] = None
    consignee: Optional[str] = None
    notify: Optional[str] = None

    bl_number: Optional[str] = None
    container_number: Optional[str] = None
    container_type: Optional[str] = None
    marks: Optional[str] = None
    seal: Optional[str] = None

    packages_quantity: Optional[int] = None
    packages_type: Optional[str] = None
    description: Optional[str] = None

    weight_kg: Optional[float] = None
    weight_lbs: Optional[float] = None


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
