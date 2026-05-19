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
                "country_code": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "spanish", "store": False},
            }
        },
    )


def bulk_index_chunks(document_id: str, chunks: list[str], country_code: str) -> None:
    client = _get_client()
    actions = [
        {
            "_index": _INDEX,
            "_id": f"{document_id}_{i}",
            "_source": {
                "document_id": document_id,
                "country_code": country_code,
                "content": unicodedata.normalize("NFC", chunk),
            },
        }
        for i, chunk in enumerate(chunks)
    ]
    bulk(client, actions)


def clear_index() -> None:
    """Delete all documents from the index without dropping the index itself."""
    client = _get_client()
    client.delete_by_query(index=_INDEX, body={"query": {"match_all": {}}}, refresh=True)


def search_documents(query: str, top_k: int = 5, country_code: str = "") -> list[str]:
    """Return unique document_ids ranked by best BM25 chunk score."""
    client = _get_client()
    resp = client.search(
        index=_INDEX,
        query={
            "bool": {
                "must": {"match": {"content": query}},
                "filter": {"term": {"country_code": country_code}},
            }
        },
        collapse={"field": "document_id"},
        size=top_k,
    )
    return [hit["_source"]["document_id"] for hit in resp["hits"]["hits"]]
