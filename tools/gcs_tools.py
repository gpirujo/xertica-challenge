import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


_COUNTRY_NAMES = {
    "CO": "Colombia",
    "MX": "Mexico",
    "PE": "Peru",
    "PA": "Panama",
    "AR": "Argentina",
    "BR": "Brazil",
    "CL": "Chile",
}


def _docs_base() -> Path:
    docs_dir = os.environ.get("DOCS_DIR", "docs")
    base = Path(docs_dir)
    if not base.is_absolute():
        base = Path(__file__).parent.parent / base
    return base.resolve()


def get_document_catalog() -> list[dict]:
    base = _docs_base()
    results = []

    for dirpath, _dirnames, filenames in os.walk(base):
        for filename in (f for f in filenames if f.endswith(".txt")):
            full_path = Path(dirpath) / filename
            rel = full_path.relative_to(base)
            parts = rel.parts  # e.g. ("CO", "UIAF", "circular", "2021", "001_ros.txt")

            country_code = parts[0] if len(parts) > 0 else ""
            issuer = parts[1] if len(parts) > 1 else ""
            doc_type = parts[2] if len(parts) > 2 else ""
            year = parts[3] if len(parts) > 3 and parts[3].isdigit() else ""

            country = _COUNTRY_NAMES.get(country_code.upper(), country_code)

            stem = Path(filename).stem  # e.g. "001_reporte_operaciones_sospechosas"
            doc_number, rest = stem.split("_", 1)
            doc_title = rest.replace("_", " ")

            results.append({
                "document_id": str(rel),
                "country": country,
                "country_code": country_code,
                "issuer": issuer,
                "type": doc_type,
                "year": year,
                "number": doc_number,
                "title": doc_title,
            })

    return results


def get_document(document_id: str) -> str:
    path = _docs_base() / document_id
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {document_id}")
    return path.read_text(encoding="utf-8")
