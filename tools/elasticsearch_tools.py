import os
import unicodedata

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

load_dotenv()

_client = None
_INDEX = "regulatory_chunks"


def _get_client() -> Elasticsearch:
    global _client
    if _client is None:
        host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
        port = int(os.environ.get("ELASTICSEARCH_PORT", 9200))
        _client = Elasticsearch(f"http://{host}:{port}")
    return _client


def ensure_index() -> None:
    client = _get_client()
    if not client.indices.exists(index=_INDEX):
        client.indices.create(
            index=_INDEX,
            settings={
                "analysis": {
                    "analyzer": {"default": {"type": "spanish"}}
                }
            },
            mappings={
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "content": {"type": "text", "analyzer": "spanish"},
                    "metadata": {"type": "object"},
                }
            },
        )


def bulk_index_chunks(
    document_id: str,
    chunks: list[str],
    metadata: dict | None = None,
) -> None:
    client = _get_client()
    actions = [
        {
            "_index": _INDEX,
            "_id": f"{document_id}_{i}",
            "_source": {
                "chunk_id": f"{document_id}_{i}",
                "document_id": document_id,
                "content": unicodedata.normalize("NFC", chunk),
                "metadata": metadata or {},
            },
        }
        for i, chunk in enumerate(chunks)
    ]
    bulk(client, actions)


def search_chunks(query: str, top_k: int = 5) -> list[str]:
    client = _get_client()
    resp = client.search(
        index=_INDEX,
        query={"match": {"content": query}},
        size=top_k,
    )
    return [hit["_source"]["content"] for hit in resp["hits"]["hits"]]
