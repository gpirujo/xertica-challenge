import logging
import re
from collections.abc import Callable

from tools import gcs_tools
from rag import dense, sparse
from rag.graph import GraphLayer

logger = logging.getLogger(__name__)

ARTICLE_RE = re.compile(
    r"^(Art[ií]culo\s+\d+|Art\.\s*\d+|ART[ÍI]CULO\s+\d+)",
    re.IGNORECASE | re.MULTILINE,
)


def index_documents(
    before: Callable[[dict], None] | None = None,
    after: Callable[[dict], None] | None = None,
) -> None:
    docs = gcs_tools.get_document_catalog()
    dense.initialize()
    sparse.initialize()
    graph_layer = GraphLayer()
    graph_layer.initialize()
    graph_layer.load_catalog(docs)

    for doc in docs:
        document_id = doc["document_id"]
        country_code = doc["country_code"]
        content = gcs_tools.get_document(document_id)

        boundaries = [m.start() for m in ARTICLE_RE.finditer(content)]
        if boundaries:
            articles = []
            for i, start in enumerate(boundaries):
                end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
                articles.append(content[start:end])
        else:
            articles = [content]

        if before is not None:
            before(doc)
        dense.index(document_id, articles, country_code)
        sparse.index(document_id, articles, country_code)
        graph_layer.index(document_id, content, country_code)
        if after is not None:
            after(doc)
