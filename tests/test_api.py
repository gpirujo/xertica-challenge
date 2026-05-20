import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_PIPELINE_STATE = {
    "risk_score": 6,
    "decision": "escalate",
    "decision_status": "done",
    "risk_justification": "test",
    "risk_summary": "summary",
    "anomalies": ["a1"],
    "confidence": 0.9,
    "applicable_regulations": [],
    "reasoning_steps": ["s1", "s2", "s3"],
    "final_report": "report",
}


class TestHealthEndpoint(unittest.TestCase):
    def test_health_returns_ok(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "compliance-agent"})


class TestAnalyzeAlert(unittest.TestCase):
    def test_analyze_alert_returns_response(self):
        with patch("api.main.run_pipeline", return_value=_PIPELINE_STATE):
            response = client.post("/api/v1/alerts/TEST-001/analyze")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["alert_id"], "TEST-001")
        self.assertEqual(body["risk_score"], 6)
        self.assertEqual(body["risk_level"], "medium")
        self.assertEqual(body["decision"], "escalate")

    def test_analyze_alert_pipeline_error(self):
        with patch("api.main.run_pipeline", side_effect=Exception("boom")):
            response = client.post("/api/v1/alerts/TEST-001/analyze")

        self.assertEqual(response.status_code, 500)


class TestAlertStatus(unittest.TestCase):
    def test_get_alert_status(self):
        response = client.get("/api/v1/alerts/TEST-001/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["alert_id"], "TEST-001")


if __name__ == "__main__":
    unittest.main()
