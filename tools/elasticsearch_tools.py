import os
import unicodedata

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError
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
    try:
        client.indices.get(index=_INDEX)
        return
    except NotFoundError:
        pass
    client.indices.create(
        index=_INDEX,
        settings={
            "analysis": {
                "analyzer": {"default": {"type": "spanish"}}
            }
        },
        mappings={
            "properties": {
                "document_id": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "spanish", "store": False},
            }
        },
    )


def bulk_index_chunks(document_id: str, chunks: list[str]) -> None:
    client = _get_client()
    actions = [
        {
            "_index": _INDEX,
            "_id": f"{document_id}_{i}",
            "_source": {
                "document_id": document_id,
                "content": unicodedata.normalize("NFC", chunk),
            },
        }
        for i, chunk in enumerate(chunks)
    ]
    bulk(client, actions)


def search_documents(query: str, top_k: int = 5) -> list[str]:
    """Return unique document_ids ranked by best BM25 chunk score."""
    client = _get_client()
    resp = client.search(
        index=_INDEX,
        query={"match": {"content": query}},
        collapse={"field": "document_id"},
        size=top_k,
    )
    return [hit["_source"]["document_id"] for hit in resp["hits"]["hits"]]
