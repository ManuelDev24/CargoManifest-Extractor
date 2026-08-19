# CargoManifest-Extractor

[![Python CI](https://github.com/ManuelDev24/CargoManifest-Extractor/actions/workflows/python-ci.yml/badge.svg)](https://github.com/ManuelDev24/CargoManifest-Extractor/actions/workflows/python-ci.yml)

Automated Python pipeline for extracting and validating structured cargo manifest data from PDF documents, with support for Excel, CSV, JSON, and future SQL Server integration.

## Ejecutar tests localmente

Se incluye un conjunto de tests unitarios mínimos que se ejecutan en CI. Para ejecutar los tests localmente:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
# Instala dependencias principales (nota: PyMuPDF puede requerir compilación en algunas plataformas)
pip install -r requirements.txt
# Instala herramientas de desarrollo para test y lint
pip install pytest flake8

# Ejecutar tests
pytest -q
```

Los tests añadidos usan fixtures ligeras y evitan importar PyMuPDF en tiempo de importación, por lo que no siempre es necesario tener PyMuPDF instalado para ejecutar el conjunto de pruebas básicas.

## CI

El workflow de GitHub Actions está en `.github/workflows/python-ci.yml` y ejecuta linting (flake8) y pytest en push/PR sobre la rama `main`.
