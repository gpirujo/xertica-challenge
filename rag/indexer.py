import logging
import re

import tiktoken

from tools import elasticsearch_tools, embedding_tools, gcs_tools, postgresql_tools

logger = logging.getLogger(__name__)

ARTICLE_RE = re.compile(
    r"^(Art[ií]culo\s+\d+|Art\.\s*\d+|ART[ÍI]CULO\s+\d+)",
    re.IGNORECASE | re.MULTILINE,
)

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


def index_documents() -> None:
    enc = tiktoken.get_encoding(_ENCODING)
    postgresql_tools.ensure_table()
    elasticsearch_tools.ensure_index()

    docs = gcs_tools.get_document_catalog()

    for doc in docs:
        filename = doc["document_id"]
        content = gcs_tools.get_document(filename)

        boundaries = [m.start() for m in ARTICLE_RE.finditer(content)]
        if boundaries:
            articles = []
            for i, start in enumerate(boundaries):
                end = boundaries[i + 1] if i + 1 < len(boundaries) else len(content)
                articles.append(content[start:end])
        else:
            articles = [content]

        all_chunks: list[str] = []
        for article in articles:
            all_chunks.extend(_split_into_chunks(article, enc))

        embeddings = embedding_tools.embed(all_chunks)
        postgresql_tools.insert_embeddings(filename, embeddings)
        elasticsearch_tools.bulk_index_chunks(filename, all_chunks, metadata=doc)

        logger.info("Indexed %s — %d chunks", filename, len(all_chunks))
