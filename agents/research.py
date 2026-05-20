import logging

from graph.state import ComplianceState
from rag.retriever import hybrid_retrieve
from tools.bigquery_tools import get_customer_data, get_latest_transactions
from tools.gcs_tools import get_document

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Collects alert context, customer profile, transaction history, and relevant regulatory documents."""

    def run(self, state: ComplianceState) -> ComplianceState:
        try:
            alert = state["alert"]
            alert_id = alert["alert_id"]
            customer_id = alert["customer_id"]

            state["customer"] = get_customer_data(customer_id)

            transactions = get_latest_transactions(customer_id, days=90)
            home_country = state["customer"]["country_code"]
            for txn in transactions:
                txn["is_international"] = txn["counterparty_country"] != home_country
            state["transaction_history"] = transactions

            if transactions:
                intl = [t for t in transactions if t["is_international"]]
                total_volume = sum(t["amount_usd"] for t in transactions)
                state["transaction_summary"] = {
                    "customer_id": customer_id,
                    "period_days": 90,
                    "total_transactions": len(transactions),
                    "total_volume_usd": total_volume,
                    "avg_transaction_usd": total_volume / len(transactions),
                    "max_transaction_usd": max(t["amount_usd"] for t in transactions),
                    "international_transactions": len(intl),
                    "international_volume_usd": sum(t["amount_usd"] for t in intl),
                    "flagged_by_xgboost": sum(1 for t in transactions if t.get("is_flagged", False)),
                }
            else:
                state["transaction_summary"] = {}

            query = f"{alert['alert_type']} {alert['description']}"
            doc_ids = hybrid_retrieve(query, country_code=state["customer"]["country_code"])

            documents = []
            for doc_id in doc_ids:
                try:
                    text = get_document(doc_id)
                    documents.append({"document_id": doc_id, "content": text})
                except FileNotFoundError:
                    logger.warning("Document not found, skipping: %s", doc_id)
            state["documents"] = documents

            state["investigador_status"] = "done"
            state["investigador_error"] = None

        except Exception as exc:
            state["investigador_status"] = "error"
            state["investigador_error"] = str(exc)

        return state
