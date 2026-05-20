import logging
from typing import Literal

from pydantic import BaseModel, Field

from graph.state import ComplianceState
from observability.langfuse_config import score_trace
from tools.llm_tools import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un juez de compliance AML/CFT con profundo conocimiento de las regulaciones "
    "de la UIAF (Colombia), la CNBV (México) y la SBS (Perú). "
    "Tu función NO es investigar ni analizar: ya eso fue hecho por los agentes anteriores. "
    "Tu única tarea es evaluar la evidencia ya reunida y emitir una decisión final sobre la alerta. "
    "Debes determinar si la evidencia es suficiente para cerrar la alerta (dismiss), "
    "si requiere intervención del oficial de compliance humano (escalate), "
    "o si se necesita información adicional antes de decidir (request_info). "
    "Los clientes clasificados como PEP (Persona Expuesta Políticamente) representan riesgo elevado "
    "según la normativa AML/CFT de Colombia, México y Perú, y deben tratarse con criterio conservador: "
    "ante la duda, escalá."
)


class DecisionOutput(BaseModel):
    decision: Literal["escalate", "dismiss", "request_info"]
    confidence: float = Field(ge=0.0, le=1.0)
    applicable_regulations: list[str] = Field(
        description="Citas de normas concretas, ej: 'UIAF Circular 009/2021 Art. 15'"
    )
    reasoning_steps: list[str] = Field(
        min_length=3,
        description="Pasos del razonamiento que conforman el audit trail (mínimo 3)"
    )
    final_report: str = Field(
        description="Resumen ejecutivo de 2–3 oraciones para el oficial de compliance humano"
    )


class DecisionAgent:
    def run(self, state: ComplianceState) -> ComplianceState:
        try:
            customer = state.get("customer", {})
            transaction_summary = state.get("transaction_summary", {})
            anomalies = state.get("anomalies", [])
            risk_score = state.get("risk_score")
            risk_justification = state.get("risk_justification", "")
            risk_summary = state.get("risk_summary", "")

            total_volume = transaction_summary.get("total_volume_usd", 0)
            max_transaction = transaction_summary.get("max_transaction_usd", 0)
            intl_transactions = transaction_summary.get("international_transactions", 0)
            total_transactions = transaction_summary.get("total_transactions", 0)
            pct_international = (
                (intl_transactions / total_transactions * 100) if total_transactions else 0.0
            )

            anomalies_text = (
                "\n".join(f"- {a}" for a in anomalies) if anomalies else "- Ninguna registrada."
            )

            prompt = f"""{SYSTEM_PROMPT}

## Perfil del cliente
- Nombre: {customer.get("name", "N/A")}
- Tipo: {customer.get("customer_type", "N/A")}
- País: {customer.get("country_code", "N/A")}
- Es PEP: {customer.get("is_pep", False)}

## Análisis de riesgo (producido por el agente anterior)
- Puntaje de riesgo: {risk_score}/10
- Justificación: {risk_justification}
- Resumen: {risk_summary}

## Anomalías detectadas
{anomalies_text}

## Resumen de transacciones (últimos 90 días)
- Volumen total (USD): {total_volume:.2f}
- Transacción máxima (USD): {max_transaction:.2f}
- Porcentaje internacional: {pct_international:.1f}%

## Instrucción
Con base exclusivamente en la información anterior, emití una decisión final sobre la alerta.
No investigues ni analices nuevamente: evaluá lo que ya está documentado.
Citá las normas aplicables con artículo específico cuando sea posible.
Tu razonamiento debe poder ser auditado, por lo que reasoning_steps debe tener al menos 3 pasos.
"""

            result: DecisionOutput = (
                get_llm().with_structured_output(DecisionOutput).invoke(prompt)
            )

            existing_regs: list[dict] = state.get("applicable_regulations") or []
            citations: list[str] = result.applicable_regulations

            # Attach each LLM citation to the first regulation whose title or
            # document_id it mentions; unmatched citations become standalone dicts.
            unmatched = list(citations)
            for reg in existing_regs:
                doc_id = reg.get("document_id", "")
                title = reg.get("title", "")
                for citation in citations:
                    if doc_id in citation or title.lower() in citation.lower():
                        reg["citation"] = citation
                        if citation in unmatched:
                            unmatched.remove(citation)
                        break

            merged = existing_regs + [{"citation": c} for c in unmatched]

            state["decision"] = result.decision
            state["confidence"] = result.confidence
            state["applicable_regulations"] = merged
            state["reasoning_steps"] = result.reasoning_steps
            state["final_report"] = result.final_report
            state["decision_status"] = "done"
            state["decision_error"] = None

            if trace_id := state.get("trace_id"):
                escalation = 1.0 if result.decision == "escalate" else 0.0
                dismissed  = 1.0 if result.decision == "dismiss"  else 0.0
                score_trace(trace_id, "escalation_decision", escalation)
                score_trace(trace_id, "auto_dismissed",       dismissed)
                score_trace(trace_id, "confidence",           result.confidence)

        except Exception as exc:
            logger.error("DecisionAgent error: %s", exc, exc_info=True)
            state["decision_status"] = "error"
            state["decision_error"] = str(exc)

        return state
