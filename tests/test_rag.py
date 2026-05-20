import unicodedata
import unittest
from unittest.mock import MagicMock, patch

import tiktoken

import rag.retriever as retriever_module
from rag import dense, sparse
from rag.dense import _OVERLAP_TOKENS, _split_into_chunks
from rag.graph import GraphLayer
from rag.indexer import index_documents
from rag.retriever import hybrid_retrieve


_ENC = tiktoken.get_encoding("cl100k_base")


class TestDenseChunking(unittest.TestCase):
    def test_split_into_chunks_single_chunk(self):
        text = "Texto corto que no supera los doscientos tokens."
        chunks = _split_into_chunks(text, _ENC)
        self.assertEqual(len(chunks), 1)

    def test_split_into_chunks_overlap(self):
        # ~300 tokens — enough for exactly 2 chunks
        text = "hello world " * 150
        chunks = _split_into_chunks(text, _ENC)
        self.assertGreaterEqual(len(chunks), 2)

        tokens_0 = _ENC.encode(chunks[0])
        overlap_text = _ENC.decode(tokens_0[-_OVERLAP_TOKENS:])
        self.assertTrue(chunks[1].startswith(overlap_text))


class TestDenseSearch(unittest.TestCase):
    def test_dense_search_calls_postgresql(self):
        fake_vector = [0.1] * 8
        fake_embeddings = MagicMock()
        fake_embeddings.embed_query.return_value = fake_vector

        with patch("rag.dense.get_embeddings", return_value=fake_embeddings), \
             patch("rag.dense.postgresql_tools.search_similar", return_value=["doc1"]) as mock_similar:
            result = dense.search("query", top_k=3, country_code="CO")

        mock_similar.assert_called_once_with(fake_vector, 3, "CO")
        self.assertEqual(result, ["doc1"])


class TestSparseSearch(unittest.TestCase):
    def test_sparse_search_normalizes_nfc(self):
        nfd_query = unicodedata.normalize("NFD", "café")
        nfc_query = unicodedata.normalize("NFC", "café")

        with patch("rag.sparse.elasticsearch_tools.search_documents", return_value=[]) as mock_search:
            sparse.search(nfd_query)

        self.assertEqual(mock_search.call_args[0][0], nfc_query)

    def test_sparse_search_passes_top_k(self):
        with patch("rag.sparse.elasticsearch_tools.search_documents", return_value=[]) as mock_search:
            sparse.search("query", top_k=7, country_code="CO")

        mock_search.assert_called_once_with("query", 7, "CO")

    def test_sparse_index_calls_bulk(self):
        with patch("rag.sparse.elasticsearch_tools.bulk_index_chunks") as mock_bulk:
            sparse.index("doc1", ["art1", "art2"], "CO")

        mock_bulk.assert_called_once_with("doc1", ["art1", "art2"], "CO")


class TestGraphLayer(unittest.TestCase):
    def test_graph_expand_returns_related(self):
        with patch("rag.graph.falkordb_tools.get_related_documents", return_value=["DOC-B"]):
            graph = GraphLayer()
            result = graph.expand("DOC-A")

        self.assertEqual(result, ["DOC-B"])

    def test_graph_expand_returns_empty(self):
        with patch("rag.graph.falkordb_tools.get_related_documents", return_value=[]):
            graph = GraphLayer()
            result = graph.expand("DOC-A")

        self.assertEqual(result, [])


class TestIndexer(unittest.TestCase):
    def test_index_documents_calls_dense_sparse_graph(self):
        doc = {
            "document_id": "CO/UIAF/circular/2021/001_ros.txt",
            "country_code": "CO",
            "country": "Colombia",
            "issuer": "UIAF",
            "type": "circular",
            "year": "2021",
            "number": "001",
            "title": "ros",
        }
        mock_graph = MagicMock()

        with patch("rag.indexer.gcs_tools.get_document_catalog", return_value=[doc]), \
             patch("rag.indexer.gcs_tools.get_document", return_value="Artículo 1 contenido"), \
             patch("rag.indexer.dense.initialize"), \
             patch("rag.indexer.dense.index") as mock_dense_index, \
             patch("rag.indexer.sparse.initialize"), \
             patch("rag.indexer.sparse.index") as mock_sparse_index, \
             patch("rag.indexer.GraphLayer", return_value=mock_graph):
            index_documents()

        mock_dense_index.assert_called_once()
        self.assertEqual(mock_dense_index.call_args[0][0], doc["document_id"])

        mock_sparse_index.assert_called_once()
        self.assertEqual(mock_sparse_index.call_args[0][0], doc["document_id"])

        mock_graph.index.assert_called_once()
        self.assertEqual(mock_graph.index.call_args[0][0], doc["document_id"])


class TestRetriever(unittest.TestCase):
    def test_hybrid_retrieve_rrf_ordering(self):
        # B appears in both lists → highest RRF score → must be first
        with patch("rag.retriever.dense.search", return_value=["A", "B"]), \
             patch("rag.retriever.sparse.search", return_value=["B", "C"]), \
             patch.object(retriever_module._graph, "expand", return_value=[]):
            result = hybrid_retrieve("query", top_k=5, country_code="CO")

        self.assertIn("B", result)
        self.assertIn("A", result)
        self.assertIn("C", result)
        self.assertLess(result.index("B"), result.index("A"))
        self.assertLess(result.index("B"), result.index("C"))

    def test_hybrid_retrieve_appends_graph_extras(self):
        def expand_side_effect(doc_id):
            return ["X"] if doc_id == "A" else []

        with patch("rag.retriever.dense.search", return_value=["A"]), \
             patch("rag.retriever.sparse.search", return_value=["A"]), \
             patch.object(retriever_module._graph, "expand", side_effect=expand_side_effect):
            result = hybrid_retrieve("query", top_k=5, country_code="CO")

        self.assertIn("X", result)
        self.assertLess(result.index("A"), result.index("X"))


if __name__ == "__main__":
    unittest.main()
