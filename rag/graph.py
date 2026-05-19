import logging

logger = logging.getLogger(__name__)


def initialize(document_catalog: list[dict]) -> None:
    logger.info("Graph.initialize called with %d documents (stub)", len(document_catalog))


def index(document_id: str, articles: list[str]) -> None:
    logger.info("Graph.index called for %s (stub)", document_id)


def expand(document_ids: list[str]) -> list[str]:
    return []
