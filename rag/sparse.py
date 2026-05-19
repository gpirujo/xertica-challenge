import logging
import unicodedata

from tools import elasticsearch_tools

logger = logging.getLogger(__name__)


def initialize() -> None:
    elasticsearch_tools.ensure_index()


def index(document_id: str, articles: list[str]) -> None:
    elasticsearch_tools.bulk_index_chunks(document_id, articles)
    logger.info("Sparse-indexed %s — %d articles", document_id, len(articles))


def search(query: str, top_k: int = 5) -> list[str]:
    normalized = unicodedata.normalize("NFC", query)
    return elasticsearch_tools.search_documents(normalized, top_k)
