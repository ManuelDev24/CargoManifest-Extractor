from __future__ import annotations
from typing import List
from dataclasses import dataclass
import re

from core.models import ManifestRecord


@dataclass
class ValidationIssue:
    record_index: int
    bl_number: str | None
    equipment_id: str | None
    field_name: str
    severity: str  # "ERROR" | "WARNING"
    message: str


@dataclass
class ValidationReport:
    total_records: int = 0
    valid_records: int = 0
    error_count: int = 0
    warning_count: int = 0
    issues: List[ValidationIssue] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


class ManifestValidator:
    @staticmethod
    def _bl_format_ok(bl: str | None) -> bool:
        if not bl:
            return False
        return bool(re.search(r"PYRR-\d+", bl))

    @staticmethod
    def _weight_coherent(kg: float | None, lbs: float | None, tol: float = 0.015) -> bool:
        # if both empty, consider coherent
        if not kg and not lbs:
            return True
        if kg and lbs:
            expected_lbs = kg * 2.20462
            if expected_lbs == 0:
                return lbs == 0
            rel_err = abs(expected_lbs - lbs) / expected_lbs
            return rel_err <= tol
        return False

    @classmethod
    def validate(cls, records: List[ManifestRecord]) -> ValidationReport:
        report = ValidationReport(total_records=len(records))
        for r in records:
            has_error = False
            # BL format
            if r.bl_number:
                if not cls._bl_format_ok(r.bl_number):
                    report.issues.append(ValidationIssue(r.record_number, r.bl_number, r.equipment_id, "bl_number", "WARNING", "B/L format unexpected"))
                    report.warning_count += 1
                else:
                    # good bl
                    pass
            else:
                report.issues.append(ValidationIssue(r.record_number, None, r.equipment_id, "bl_number", "ERROR", "Missing B/L number"))
                report.error_count += 1
                has_error = True

            # weight coherence
            if not cls._weight_coherent(r.weight_kg, r.weight_lbs):
                report.issues.append(ValidationIssue(r.record_number, r.bl_number, r.equipment_id, "weight", "WARNING", "Weight KG/LBS not coherent or missing"))
                report.warning_count += 1

            # minimal mandatory fields
            if not r.ship_name or not r.loading_port or not r.discharge_port:
                report.issues.append(ValidationIssue(r.record_number, r.bl_number, r.equipment_id, "required_fields", "ERROR", "Missing mandatory header fields"))
                report.error_count += 1
                has_error = True

            if not has_error:
                report.valid_records += 1

        return report
