import json
from typing import List
from pathlib import Path

from core.models import ManifestRecord


class JsonExporter:
    @staticmethod
    def export(records: List[ManifestRecord], output_path: str):
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = [rec.to_dict() for rec in records]
        with open(out, mode="w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
