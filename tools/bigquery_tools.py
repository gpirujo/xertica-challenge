import json
import os
from pathlib import Path

_FIXTURES = Path(__file__).parent.parent / "fixtures"


class _MockBigQueryBackend:
    def __init__(self):
        alerts_raw = json.loads((_FIXTURES / "alerts.json").read_text(encoding="utf-8"))
        self._alerts = {a["alert_id"]: a for a in alerts_raw}

    def get_alert(self, alert_id: str) -> dict:
        if alert_id not in self._alerts:
            raise KeyError(f"Alert not found: {alert_id}")
        return self._alerts[alert_id]

    def get_customer(self, customer_id: str) -> dict:
        path = _FIXTURES / "customers" / f"{customer_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if k != "transactions"}

    def get_transactions(self, customer_id: str, days: int) -> list[dict]:
        path = _FIXTURES / "customers" / f"{customer_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["transactions"]


class _BigQueryBackend:
    def get_alert(self, alert_id: str) -> dict:
        raise NotImplementedError("Implement with real BigQuery client")

    def get_customer(self, customer_id: str) -> dict:
        raise NotImplementedError("Implement with real BigQuery client")

    def get_transactions(self, customer_id: str, days: int) -> list[dict]:
        raise NotImplementedError("Implement with real BigQuery client")


_backend = _MockBigQueryBackend() if os.environ.get("BQ_BACKEND", "mock") == "mock" else _BigQueryBackend()


def get_alert_data(alert_id: str) -> dict:
    return _backend.get_alert(alert_id)


def get_customer_data(customer_id: str) -> dict:
    return _backend.get_customer(customer_id)


def get_latest_transactions(customer_id: str, days: int = 90) -> list[dict]:
    return _backend.get_transactions(customer_id, days)
