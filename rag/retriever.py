import logging

from rag import dense, sparse
from rag.graph import GraphLayer

logger = logging.getLogger(__name__)

_graph = GraphLayer()


def initialize() -> None:
    _graph.initialize()


def hybrid_retrieve(query: str, top_k: int = 5, country_code: str = "") -> list[str]:
    dense_results = dense.search(query, top_k=top_k, country_code=country_code)
    sparse_results = sparse.search(query, top_k=top_k, country_code=country_code)

    scores: dict[str, float] = {}
    for rank, doc_id in enumerate(dense_results):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (60 + rank)
    for rank, doc_id in enumerate(sparse_results):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (60 + rank)

    rrf_list = sorted(scores, key=lambda d: scores[d], reverse=True)[:top_k]

    rrf_set = set(rrf_list)
    graph_extras: list[str] = []
    for doc_id in rrf_list:
        for related in _graph.expand(doc_id):
            if related not in rrf_set and related not in graph_extras:
                graph_extras.append(related)

    return rrf_list + graph_extras
