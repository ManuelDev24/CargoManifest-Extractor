from enum import Enum

class ManifestType(str, Enum):
    LOCAL = "LOCAL"
    PUERTO_RICO = "PUERTO_RICO"
    UNKNOWN = "UNKNOWN"

# Later additions:
# ManifestRecord
# ManifestAnalysis
# ValidationResult
