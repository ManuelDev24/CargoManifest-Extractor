import csv
from typing import List
from pathlib import Path

from core.models import ManifestRecord


class CsvExporter:
    @staticmethod
    def export(records: List[ManifestRecord], output_path: str):
        if not records:
            return

        headers = list(records[0].to_dict().keys())
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for rec in records:
                writer.writerow(rec.to_dict())
