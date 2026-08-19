from pathlib import Path

from core.models import ManifestType
from core.pdf_reader import read_pdf
from core.pdf_detector import analyze_pdf_structure

INPUT_DIR = Path("data/input")


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

    for pdf_path in pdf_files:

        print("-" * 80)
        print(f"Archivo: {pdf_path.name}")
        print("-" * 80)

        document = read_pdf(pdf_path)

        analysis = analyze_pdf_structure(document)

        detected = analysis.get("detected_type", ManifestType.UNKNOWN)
        detected_label = detected.value if isinstance(detected, ManifestType) else str(detected)

        print(f"Páginas       : {analysis['pages']}")
        print(f"Palabras      : {analysis['total_words']}")
        print(f"Palabras únicas: {analysis['unique_words']}")
        print(f"Tipo detectado: {detected_label}")
        print(f"Confianza     : {analysis.get('confidence', 0.0):.1f}%")
        print(f"Riesgo        : {analysis.get('risk', 'unknown').upper()}")

        print("\nPalabras más frecuentes:")

        for word, count in analysis["top_words"]:
            print(f"  {count:5d}  {word}")

        print()


if __name__ == "__main__":
    main()
