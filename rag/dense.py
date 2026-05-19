import logging

import tiktoken

from tools import llm_tools, postgresql_tools

logger = logging.getLogger(__name__)

_CHUNK_TOKENS = 200
_OVERLAP_TOKENS = 40
_ENCODING = "cl100k_base"


def _split_into_chunks(text: str, encoding: tiktoken.Encoding) -> list[str]:
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + _CHUNK_TOKENS
        chunk_tokens = tokens[start:end]
        chunks.append(encoding.decode(chunk_tokens))
        if end >= len(tokens):
            break
        start += _CHUNK_TOKENS - _OVERLAP_TOKENS
    return chunks


def initialize() -> None:
    postgresql_tools.ensure_table()


def index(document_id: str, articles: list[str], country_code: str) -> None:
    enc = tiktoken.get_encoding(_ENCODING)
    all_chunks: list[str] = []
    for article in articles:
        all_chunks.extend(_split_into_chunks(article, enc))
    embeddings = llm_tools.embed(all_chunks)
    postgresql_tools.insert_embeddings(document_id, embeddings, country_code)
    logger.info("Dense-indexed %s — %d chunks", document_id, len(all_chunks))


def search(query: str, top_k: int = 5, country_code: str = "") -> list[str]:
    query_embedding = llm_tools.embed([query])
    return postgresql_tools.search_similar(query_embedding[0], top_k, country_code)
