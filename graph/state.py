from typing import Any, Literal
from typing_extensions import TypedDict


AgentStatus = Literal["pending", "running", "done", "error"]


class ComplianceState(TypedDict, total=False):
    # Input
    alert: dict[str, Any]

    # Agente Investigador
    customer: dict[str, Any]
    transaction_history: list[dict[str, Any]]
    transaction_summary: dict[str, Any]
    documents: list[dict[str, Any]]
    investigador_status: AgentStatus
    investigador_error: str | None

    # Agente de Riesgo
    risk_score: int                      # 1–10
    risk_justification: str
    anomalies: list[str]
    risk_summary: str
    risk_analyzer_status: AgentStatus
    risk_analyzer_error: str | None

    # Agente de Decisión
    decision: Literal["escalate", "dismiss", "request_info"]
    confidence: float                    # 0.0 – 1.0
    applicable_regulations: list[dict[str, Any]]
    reasoning_steps: list[str]
    final_report: str
    decision_status: AgentStatus
    decision_error: str | None
