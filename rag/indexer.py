import logging
import re

from tools import gcs_tools
from rag import dense, graph, sparse

logger = logging.getLogger(__name__)

ARTICLE_RE = re.compile(
    r"^(Art[ií]culo\s+\d+|Art\.\s*\d+|ART[ÍI]CULO\s+\d+)",
    re.IGNORECASE | re.MULTILINE,
)


def index_documents() -> None:
    docs = gcs_tools.get_document_catalog()
    dense.initialize()
    sparse.initialize()
    graph.initialize(docs)

    for doc in docs:
        document_id = doc["document_id"]
        content = gcs_tools.get_document(document_id)

        boundaries = [m.start() for m in ARTICLE_RE.finditer(content)]
        if boundaries:
            articles = []
            for i, start in enumerate(boundaries):
                end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
                articles.append(content[start:end])
        else:
            articles = [content]

        dense.index(document_id, articles)
        sparse.index(document_id, articles)
        graph.index(document_id, articles)
