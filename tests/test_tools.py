import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from tools.bigquery_tools import get_alert_data, get_customer_data, get_latest_transactions
from tools.elasticsearch_tools import bulk_index_chunks, search_documents
from tools.falkordb_tools import create_edge, get_related_documents
from tools.gcs_tools import get_document, get_document_catalog, get_document_metadata
from tools.postgresql_tools import insert_embeddings, search_similar


class TestBigqueryTools(unittest.TestCase):
    def test_get_alert_data_is_deterministic(self):
        result1 = get_alert_data("ALERT-001")
        result2 = get_alert_data("ALERT-001")
        self.assertEqual(result1, result2)

    def test_get_alert_data_fields(self):
        result = get_alert_data("ALERT-XYZ")
        for key in ("alert_id", "customer_id", "alert_type", "description", "severity", "created_at"):
            self.assertIn(key, result)

    def test_get_customer_data_is_pep_deterministic(self):
        result1 = get_customer_data("CUST-001")
        result2 = get_customer_data("CUST-001")
        self.assertEqual(result1["is_pep"], result2["is_pep"])

    def test_get_latest_transactions_returns_list(self):
        txns = get_latest_transactions("CUST-001")
        self.assertGreater(len(txns), 0)
        for key in ("transaction_id", "amount_usd", "counterparty_country"):
            self.assertIn(key, txns[0])


class TestGcsTools(unittest.TestCase):
    def test_get_document_metadata_parses_path(self):
        meta = get_document_metadata("CO/UIAF/circular/2021/001_ros.txt")
        self.assertEqual(meta["country_code"], "CO")
        self.assertEqual(meta["issuer"], "UIAF")
        self.assertEqual(meta["type"], "circular")
        self.assertEqual(meta["year"], "2021")
        self.assertEqual(meta["number"], "001")

    def test_get_document_raises_on_missing(self):
        with self.assertRaises(FileNotFoundError):
            get_document("no/existe.txt")

    def test_get_document_catalog_returns_list(self):
        fake_base = Path("/fake/docs")
        fake_dirpath = str(fake_base / "CO" / "UIAF" / "circular" / "2021")

        with patch("tools.gcs_tools._docs_base", return_value=fake_base), \
             patch("tools.gcs_tools.os.walk", return_value=[(fake_dirpath, [], ["001_ros.txt"])]):
            catalog = get_document_catalog()

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["document_id"], str(Path("CO/UIAF/circular/2021/001_ros.txt")))


class TestElasticsearchTools(unittest.TestCase):
    def test_search_documents_calls_client(self):
        fake_client = MagicMock()
        fake_client.search.return_value = {"hits": {"hits": []}}

        with patch("tools.elasticsearch_tools._get_client", return_value=fake_client):
            result = search_documents("lavado de activos", country_code="CO")

        fake_client.search.assert_called_once()
        kwargs = fake_client.search.call_args.kwargs
        self.assertEqual(kwargs["index"], "regulatory_chunks")
        self.assertEqual(result, [])

    def test_bulk_index_chunks_ids(self):
        fake_client = MagicMock()
        chunks = ["chunk0", "chunk1", "chunk2"]

        with patch("tools.elasticsearch_tools._get_client", return_value=fake_client), \
             patch("tools.elasticsearch_tools.bulk") as mock_bulk:
            bulk_index_chunks("doc1", chunks, "CO")

        mock_bulk.assert_called_once()
        actions = mock_bulk.call_args[0][1]
        self.assertEqual(len(actions), 3)
        for i, action in enumerate(actions):
            self.assertEqual(action["_id"], f"doc1_{i}")


class TestPostgresqlTools(unittest.TestCase):
    def _make_fake_conn(self, fetchall_return=None):
        fake_cursor = MagicMock()
        fake_cursor.fetchall.return_value = fetchall_return or []
        fake_conn = MagicMock()
        fake_conn.cursor.return_value.__enter__ = lambda s: fake_cursor
        fake_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return fake_conn, fake_cursor

    def test_search_similar_returns_filenames(self):
        fake_conn, _ = self._make_fake_conn(fetchall_return=[("doc1.txt",), ("doc2.txt",)])

        with patch("tools.postgresql_tools._get_connection", return_value=fake_conn):
            result = search_similar([0.1, 0.2, 0.3], top_k=2, country_code="CO")

        self.assertEqual(result, ["doc1.txt", "doc2.txt"])

    def test_insert_embeddings_calls_executemany(self):
        fake_conn, fake_cursor = self._make_fake_conn()
        embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        with patch("tools.postgresql_tools._get_connection", return_value=fake_conn):
            insert_embeddings("doc1.txt", embeddings, "CO")

        fake_cursor.executemany.assert_called_once()
        rows = fake_cursor.executemany.call_args[0][1]
        self.assertEqual(len(rows), 3)


class TestFalkordbTools(unittest.TestCase):
    def test_get_related_documents_empty(self):
        fake_result = MagicMock()
        fake_result.result_set = []
        fake_graph = MagicMock()
        fake_graph.query.return_value = fake_result

        with patch("tools.falkordb_tools._get_graph", return_value=fake_graph):
            result = get_related_documents("doc1")

        self.assertEqual(result, [])

    def test_create_edge_calls_query(self):
        fake_graph = MagicMock()

        with patch("tools.falkordb_tools._get_graph", return_value=fake_graph):
            create_edge("doc1", "doc2", "forward")

        fake_graph.query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
