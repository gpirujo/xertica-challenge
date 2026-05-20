import logging

from pydantic import BaseModel, Field

from graph.state import ComplianceState
from tools.llm_tools import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un experto en compliance AML/CFT con profundo conocimiento de las regulaciones "
    "de la UIAF (Colombia), la CNBV (México) y la SBS (Perú). "
    "Tu función es evaluar el riesgo de lavado de activos y financiamiento del terrorismo "
    "de clientes y transacciones, identificar anomalías, y producir análisis estructurados "
    "que apoyen la toma de decisiones de los oficiales de cumplimiento."
)


class RiskAnalysisOutput(BaseModel):
    risk_score: int = Field(ge=1, le=10)
    risk_justification: str
    anomalies: list[str]
    risk_summary: str


class RiskAnalyzerAgent:
    def run(self, state: ComplianceState) -> ComplianceState:
        try:
            transaction_summary = state.get("transaction_summary", {})
            transaction_history = state.get("transaction_history", [])
            customer = state.get("customer", {})
            documents = state.get("documents", [])

            top_transactions = sorted(
                transaction_history, key=lambda t: t.get("amount_usd", 0), reverse=True
            )[:10]

            doc_excerpts = "\n\n".join(
                f"[Documento {i + 1}]\n{doc['content'][:500]}"
                for i, doc in enumerate(documents)
            )

            prompt = f"""{SYSTEM_PROMPT}

## Perfil del cliente
- Nombre: {customer.get("name", "N/A")}
- Tipo: {customer.get("customer_type", "N/A")}
- País: {customer.get("country_code", "N/A")}
- Es PEP: {customer.get("is_pep", False)}

## Resumen de transacciones (últimos 90 días)
- Total de transacciones: {transaction_summary.get("total_transactions", 0)}
- Volumen total (USD): {transaction_summary.get("total_volume_usd", 0):.2f}
- Promedio por transacción (USD): {transaction_summary.get("avg_transaction_usd", 0):.2f}
- Transacción máxima (USD): {transaction_summary.get("max_transaction_usd", 0):.2f}
- Transacciones internacionales: {transaction_summary.get("international_transactions", 0)}
- Volumen internacional (USD): {transaction_summary.get("international_volume_usd", 0):.2f}
- Marcadas por modelo XGBoost: {transaction_summary.get("flagged_by_xgboost", 0)}

## Top 10 transacciones por monto
{chr(10).join(
    f"- {t.get('transaction_date', 'N/A')} | {t.get('amount_usd', 0):.2f} USD | "
    f"País contraparte: {t.get('counterparty_country', 'N/A')} | "
    f"Internacional: {t.get('is_international', False)} | "
    f"Flagged: {t.get('is_flagged', False)}"
    for t in top_transactions
) or "Sin transacciones."}

## Documentos regulatorios relevantes
{doc_excerpts or "Sin documentos."}

## Instrucción
Analizá el perfil y las transacciones del cliente a la luz de la normativa AML/CFT aplicable.
Asigná un puntaje de riesgo del 1 (mínimo riesgo) al 10 (máximo riesgo).
Identificá anomalías específicas y producí un resumen ejecutivo de 2-3 oraciones para el analista humano.
"""

            result: RiskAnalysisOutput = (
                get_llm().with_structured_output(RiskAnalysisOutput).invoke(prompt)
            )

            state["risk_score"] = result.risk_score
            state["risk_justification"] = result.risk_justification
            state["anomalies"] = result.anomalies
            state["risk_summary"] = result.risk_summary
            state["risk_analyzer_status"] = "done"
            state["risk_analyzer_error"] = None

        except Exception as exc:
            logger.error("RiskAnalyzerAgent error: %s", exc, exc_info=True)
            state["risk_analyzer_status"] = "error"
            state["risk_analyzer_error"] = str(exc)

        return state
