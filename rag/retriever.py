import unicodedata

from tools import elasticsearch_tools, embedding_tools, postgresql_tools

# TODO: add hybrid_retrieve(query, top_k) combining dense and sparse results (RRF or weighted)


def dense_retrieve(query: str, top_k: int = 5) -> list[str]:
    query_embedding = embedding_tools.embed([query])
    return postgresql_tools.search_similar(query_embedding[0], top_k)


def sparse_retrieve(query: str, top_k: int = 5) -> list[str]:
    normalized = unicodedata.normalize("NFC", query)
    return elasticsearch_tools.search_chunks(normalized, top_k)
