import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class _MockGCSBackend:
    _COUNTRY_NAMES = {
        "CO": "Colombia",
        "MX": "Mexico",
        "PE": "Peru",
        "PA": "Panama",
        "AR": "Argentina",
        "BR": "Brazil",
        "CL": "Chile",
    }

    def _docs_base(self) -> Path:
        docs_dir = os.environ.get("DOCS_DIR", "fixtures/regulatory_docs")
        base = Path(docs_dir)
        if not base.is_absolute():
            base = Path(__file__).parent.parent / base
        return base.resolve()

    def get_document(self, document_id: str) -> str:
        path = self._docs_base() / document_id
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {document_id}")
        return path.read_text(encoding="utf-8")

    def get_document_catalog(self) -> list[dict]:
        base = self._docs_base()
        results = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in (f for f in filenames if f.endswith(".txt")):
                full_path = Path(dirpath) / filename
                rel = str(full_path.relative_to(base))
                results.append(self._document_metadata(rel))
        return results

    def _document_metadata(self, document_id: str, include_content: bool = False) -> dict:
        parts = Path(document_id).parts

        country_code = parts[0] if len(parts) > 0 else ""
        issuer = parts[1] if len(parts) > 1 else ""
        doc_type = parts[2] if len(parts) > 2 else ""
        year = parts[3] if len(parts) > 3 and parts[3].isdigit() else ""

        country = self._COUNTRY_NAMES.get(country_code.upper(), country_code)

        stem = Path(parts[-1]).stem if parts else ""
        doc_number, _, rest = stem.partition("_")
        doc_title = rest.replace("_", " ")

        metadata = {
            "document_id": document_id,
            "country_code": country_code,
            "country": country,
            "issuer": issuer,
            "type": doc_type,
            "year": year,
            "number": doc_number,
            "title": doc_title,
        }

        if include_content:
            metadata["content"] = self.get_document(document_id)

        return metadata


class _GCSBackend:
    def get_document(self, document_id: str) -> str:
        raise NotImplementedError("Implement with real GCS client")

    def get_document_catalog(self) -> list[dict]:
        raise NotImplementedError("Implement with real GCS client")


_backend = _MockGCSBackend() if os.environ.get("GCS_BACKEND", "mock") == "mock" else _GCSBackend()


def get_document_metadata(document_id: str, include_content: bool = False) -> dict:
    return _backend._document_metadata(document_id, include_content)


def get_document_catalog() -> list[dict]:
    return _backend.get_document_catalog()


def get_document(document_id: str) -> str:
    return _backend.get_document(document_id)
