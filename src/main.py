from pathlib import Path

from core.models import ManifestType
from core.pdf_reader import read_pdf
from core.pdf_detector import analyze_pdf_structure, detect_manifest_type
from parsers.local_parser import LocalManifestParser
from parsers.puerto_rico_parser import PuertoRicoManifestParser
from validators.manifest_validator import ManifestValidator
from exporters.csv_exporter import CsvExporter
from exporters.json_exporter import JsonExporter
from exporters.excel_exporter import ExcelExporter

INPUT_DIR = Path("data/input")
OUTPUT_DIR = Path("data/output")


def main() -> None:

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No se encontraron archivos PDF.")
        return

    print("=" * 80)
    print("CARGO MANIFEST DATA PIPELINE")
    print("PDF FORMAT ANALYZER")
    print("=" * 80)

    print(f"\nPDF encontrados: {len(pdf_files)}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdf_files:

        print("-" * 80)
        print(f"Archivo: {pdf_path.name}")
        print("-" * 80)

        document = read_pdf(pdf_path)

        analysis = analyze_pdf_structure(document)

        detected, confidence = detect_manifest_type(document)
        detected_label = detected.value if isinstance(detected, ManifestType) else str(detected)

        print(f"Tipo detectado: {detected_label} ({confidence}%)")

        # choose parser
        if detected == ManifestType.RD:
            parser = LocalManifestParser()
        elif detected == ManifestType.PUERTO_RICO:
            parser = PuertoRicoManifestParser()
        else:
            print("Formato desconocido — omitiendo")
            continue

        records = parser.parse(document)
        print(f"Registros extraídos: {len(records)}")

        # validate
        validation = ManifestValidator.validate(records)
        print(f"Validación: {'OK' if validation.is_valid else 'ERRORES'} | validos={validation.valid_records}/{validation.total_records} errors={validation.error_count} warnings={validation.warning_count}")

        base_name = pdf_path.stem
        excel_out = OUTPUT_DIR / f"{base_name}_extracted.xlsx"
        csv_out = OUTPUT_DIR / f"{base_name}_extracted.csv"
        json_out = OUTPUT_DIR / f"{base_name}_extracted.json"

        ExcelExporter.export(records, validation, str(excel_out))
        CsvExporter.export(records, str(csv_out))
        JsonExporter.export(records, str(json_out))

        print(f"Exportados: {excel_out}, {csv_out}, {json_out}")


if __name__ == "__main__":
    main()
