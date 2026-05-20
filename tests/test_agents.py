import unittest
from unittest.mock import MagicMock, patch

from agents.decision import DecisionAgent, DecisionOutput
from agents.research import ResearchAgent
from agents.risk_analyzer import RiskAnalysisOutput, RiskAnalyzerAgent
from graph.state import ComplianceState


_ALERT = {
    "alert_id": "ALT-001",
    "customer_id": "CUST-001",
    "alert_type": "structuring",
    "description": "Depósitos fraccionados bajo umbral.",
}

_CUSTOMER = {
    "customer_id": "CUST-001",
    "name": "Valentina Ríos",
    "country_code": "CO",
    "is_pep": False,
    "risk_profile": "medium",
    "account_type": "personal",
}

_TRANSACTIONS = [
    {
        "transaction_id": "TXN-0001",
        "customer_id": "CUST-001",
        "date": "2024-11-03",
        "amount_usd": 9800.0,
        "counterparty_country": "PA",
        "is_flagged": True,
    },
    {
        "transaction_id": "TXN-0002",
        "customer_id": "CUST-001",
        "date": "2024-11-07",
        "amount_usd": 3000.0,
        "counterparty_country": "CO",
        "is_flagged": False,
    },
]

_TRANSACTION_SUMMARY = {
    "total_transactions": 2,
    "total_volume_usd": 12800.0,
    "avg_transaction_usd": 6400.0,
    "max_transaction_usd": 9800.0,
    "international_transactions": 1,
    "international_volume_usd": 9800.0,
    "flagged_by_xgboost": 1,
}


def _make_llm_mock(output):
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = output
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain
    return mock_llm


class TestResearchAgent(unittest.TestCase):
    def _base_patches(self):
        return (
            patch("agents.research.get_customer_data", return_value=_CUSTOMER),
            patch("agents.research.get_latest_transactions", return_value=list(_TRANSACTIONS)),
            patch(
                "agents.research.hybrid_retrieve",
                return_value=["CO/UIAF/circular/2021/001_ros.txt"],
            ),
            patch("agents.research.get_document", return_value="Artículo 1 contenido."),
        )

    def test_research_agent_happy_path(self):
        state: ComplianceState = {"alert": _ALERT}
        patches = self._base_patches()
        with patches[0], patches[1], patches[2], patches[3]:
            result = ResearchAgent().run(state)

        for key in ("customer", "transaction_history", "transaction_summary", "documents"):
            self.assertIn(key, result)
        self.assertEqual(result["investigador_status"], "done")
        self.assertIsNone(result["investigador_error"])
        self.assertEqual(len(result["documents"]), 1)
        self.assertEqual(result["documents"][0]["document_id"], "CO/UIAF/circular/2021/001_ros.txt")

    def test_research_agent_sets_is_international(self):
        state: ComplianceState = {"alert": _ALERT}
        patches = self._base_patches()
        with patches[0], patches[1], patches[2], patches[3]:
            result = ResearchAgent().run(state)

        for txn in result["transaction_history"]:
            self.assertIn("is_international", txn)

        # PA != CO → international; CO == CO → domestic
        by_id = {t["transaction_id"]: t for t in result["transaction_history"]}
        self.assertTrue(by_id["TXN-0001"]["is_international"])
        self.assertFalse(by_id["TXN-0002"]["is_international"])

    def test_research_agent_error_handling(self):
        state: ComplianceState = {"alert": _ALERT}
        with patch("agents.research.get_customer_data", side_effect=Exception("db error")):
            result = ResearchAgent().run(state)

        self.assertEqual(result["investigador_status"], "error")
        self.assertEqual(result["investigador_error"], "db error")


class TestRiskAnalyzerAgent(unittest.TestCase):
    def _base_state(self) -> ComplianceState:
        return {
            "alert": _ALERT,
            "customer": _CUSTOMER,
            "transaction_summary": _TRANSACTION_SUMMARY,
            "transaction_history": list(_TRANSACTIONS),
            "documents": [
                {"document_id": "CO/UIAF/circular/2021/001_ros.txt", "content": "Artículo 1 contenido."}
            ],
        }

    def test_risk_analyzer_populates_state(self):
        output = RiskAnalysisOutput(
            risk_score=7,
            risk_justification="test justification",
            anomalies=["anomaly1"],
            risk_summary="summary",
            applicable_regulation_ids=[],
        )
        state = self._base_state()
        with patch("agents.risk_analyzer.get_llm", return_value=_make_llm_mock(output)):
            result = RiskAnalyzerAgent().run(state)

        self.assertEqual(result["risk_score"], 7)
        self.assertEqual(result["risk_analyzer_status"], "done")
        self.assertIsNone(result["risk_analyzer_error"])
        self.assertIn("anomalies", result)
        self.assertIn("risk_summary", result)

    def test_risk_analyzer_error_handling(self):
        state = self._base_state()
        with patch("agents.risk_analyzer.get_llm", side_effect=Exception("llm error")):
            result = RiskAnalyzerAgent().run(state)

        self.assertEqual(result["risk_analyzer_status"], "error")
        self.assertEqual(result["risk_analyzer_error"], "llm error")


class TestDecisionAgent(unittest.TestCase):
    def _base_state(self) -> ComplianceState:
        return {
            "alert": _ALERT,
            "customer": _CUSTOMER,
            "transaction_summary": _TRANSACTION_SUMMARY,
            "risk_score": 5,
            "risk_justification": "justification",
            "risk_summary": "summary",
            "anomalies": [],
            "applicable_regulations": [],
        }

    def test_decision_agent_populates_state(self):
        output = DecisionOutput(
            decision="escalate",
            confidence=0.9,
            applicable_regulations=[],
            reasoning_steps=["s1", "s2", "s3"],
            final_report="report",
        )
        state = self._base_state()
        with patch("agents.decision.get_llm", return_value=_make_llm_mock(output)):
            result = DecisionAgent().run(state)

        self.assertEqual(result["decision"], "escalate")
        self.assertAlmostEqual(result["confidence"], 0.9)
        self.assertEqual(result["decision_status"], "done")
        self.assertIsNone(result["decision_error"])

    def test_decision_agent_merges_regulations(self):
        doc_id = "CO/UIAF/circular/2021/001_ros.txt"
        citation = f"{doc_id} Art. 3"
        output = DecisionOutput(
            decision="escalate",
            confidence=0.8,
            applicable_regulations=[citation],
            reasoning_steps=["s1", "s2", "s3"],
            final_report="report",
        )
        state = self._base_state()
        state["applicable_regulations"] = [{"document_id": doc_id, "title": "ros"}]

        with patch("agents.decision.get_llm", return_value=_make_llm_mock(output)):
            result = DecisionAgent().run(state)

        reg = next(
            (r for r in result["applicable_regulations"] if r.get("document_id") == doc_id),
            None,
        )
        self.assertIsNotNone(reg)
        self.assertEqual(reg["citation"], citation)

    def test_decision_agent_error_handling(self):
        state = self._base_state()
        with patch("agents.decision.get_llm", side_effect=Exception("llm error")):
            result = DecisionAgent().run(state)

        self.assertEqual(result["decision_status"], "error")


if __name__ == "__main__":
    unittest.main()
