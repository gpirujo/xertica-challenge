import unicodedata
from unittest.mock import patch

import rag.indexer
import rag.retriever
from rag.indexer import index_documents
from rag.retriever import sparse_retrieve


# ---------------------------------------------------------------------------
# sparse_retrieve
# ---------------------------------------------------------------------------


def test_sparse_retrieve_returns_chunk_contents():
    expected = ["chunk A", "chunk B"]
    with patch("rag.retriever.elasticsearch_tools.search_documents", return_value=expected) as mock_search:
        result = sparse_retrieve("persona políticamente expuesta")

        mock_search.assert_called_once_with("persona políticamente expuesta", 5)
        assert result == expected


def test_sparse_retrieve_normalizes_query_to_nfc():
    """NFC-normalized form must be forwarded to search_documents."""
    raw_query = "políticamente"  # NFD: 'i' + combining acute accent
    nfc_query = unicodedata.normalize("NFC", raw_query)

    with patch("rag.retriever.elasticsearch_tools.search_documents", return_value=[]) as mock_search:
        sparse_retrieve(raw_query)

        mock_search.assert_called_once_with(nfc_query, 5)


def test_sparse_retrieve_respects_top_k():
    with patch("rag.retriever.elasticsearch_tools.search_documents", return_value=[]) as mock_search:
        sparse_retrieve("transferencia", top_k=3)

        mock_search.assert_called_once_with("transferencia", 3)


# ---------------------------------------------------------------------------
# index_documents — must write to both pgvector and Elasticsearch
# ---------------------------------------------------------------------------


def test_index_documents_calls_both_stores():
    fake_doc = {
        "document_id": "CO/UIAF/circular/2021/001_ros.txt",
        "country": "Colombia",
        "country_code": "CO",
        "issuer": "UIAF",
        "type": "circular",
        "year": "2021",
        "number": "001",
        "title": "ros",
    }
    fake_text = "Artículo 1 contenido del artículo uno."
    fake_embedding = [[0.1] * 768]

    with (
        patch("rag.indexer.gcs_tools.get_document_catalog", return_value=[fake_doc]),
        patch("rag.indexer.gcs_tools.get_document", return_value=fake_text),
        patch("rag.indexer.embedding_tools.embed", return_value=fake_embedding),
        patch("rag.indexer.postgresql_tools.ensure_table") as mock_ensure_pg,
        patch("rag.indexer.postgresql_tools.insert_embeddings") as mock_pg,
        patch("rag.indexer.elasticsearch_tools.ensure_index") as mock_ensure_es,
        patch("rag.indexer.elasticsearch_tools.bulk_index_chunks") as mock_es,
    ):
        index_documents()

        mock_ensure_pg.assert_called_once()
        mock_ensure_es.assert_called_once()
        mock_pg.assert_called_once()
        mock_es.assert_called_once()

        pg_filename = mock_pg.call_args[0][0]
        es_filename = mock_es.call_args[0][0]
        assert pg_filename == es_filename == fake_doc["document_id"]
