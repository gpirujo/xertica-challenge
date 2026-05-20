import asyncio
import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional, List, Any

from graph.pipeline import run_pipeline

app = FastAPI(title="Compliance Agent API", version="1.0.0")


class AlertRequest(BaseModel):
    customer_id: Optional[str] = None
    alert_type: Optional[str] = None
    description: Optional[str] = None


class AlertResponse(BaseModel):
    alert_id: str
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_justification: Optional[str] = None
    risk_summary: Optional[str] = None
    anomalies: Optional[List[str]] = None
    decision: Optional[str] = None
    confidence: Optional[float] = None
    applicable_regulations: Optional[List[Any]] = None
    reasoning_steps: Optional[List[str]] = None
    final_report: Optional[str] = None
    decision_status: Optional[str] = None
    decision_error: Optional[str] = None
    trace_id: Optional[str] = None


def _risk_score_to_level(score: Optional[int]) -> Optional[str]:
    if score is None:
        return None
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


@app.post("/api/v1/alerts/{alert_id}/analyze", response_model=AlertResponse)
async def analyze_alert(alert_id: str, body: AlertRequest = AlertRequest()):
    alert = {
        "alert_id": alert_id,
        "customer_id": body.customer_id or alert_id,
        "alert_type": body.alert_type or "unknown",
        "description": body.description or "",
    }
    try:
        state = await run_in_threadpool(run_pipeline, alert)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    risk_score = state.get("risk_score")
    return AlertResponse(
        alert_id=alert_id,
        risk_score=risk_score,
        risk_level=_risk_score_to_level(risk_score),
        risk_justification=state.get("risk_justification"),
        risk_summary=state.get("risk_summary"),
        anomalies=state.get("anomalies"),
        decision=state.get("decision"),
        confidence=state.get("confidence"),
        applicable_regulations=state.get("applicable_regulations"),
        reasoning_steps=state.get("reasoning_steps"),
        final_report=state.get("final_report"),
        decision_status=state.get("decision_status"),
        decision_error=state.get("decision_error"),
        trace_id=state.get("trace_id"),
    )


@app.get("/api/v1/alerts/{alert_id}/status")
async def get_alert_status(alert_id: str):
    return {
        "alert_id": alert_id,
        "status": "no_persistence",
        "message": "Use POST /analyze to process an alert. Persistence not implemented yet.",
    }


@app.get("/api/v1/metrics/summary")
async def metrics_summary(from_date: Optional[str] = None, to_date: Optional[str] = None):
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return {"error": "Langfuse not configured"}

    from observability.langfuse_config import langfuse_client

    now = datetime.utcnow()
    if not to_date:
        to_date = now.date().isoformat()
    if not from_date:
        from_date = (now - timedelta(days=30)).date().isoformat()

    async def _get(**kwargs):
        try:
            return await langfuse_client.async_api.metrics.get(
                from_timestamp=from_date,
                to_timestamp=to_date,
                **kwargs,
            )
        except Exception:
            return None

    (
        r_latency,
        r_cost,
        r_tokens,
        r_escalation,
        r_risk,
        r_error_rate,
        r_dismissed,
        r_agent_latency,
    ) = await asyncio.gather(
        _get(
            view="observations",
            measure="latency",
            aggregation="p95",
            filter=[{"column": "name", "operator": "=", "value": "compliance-pipeline"}],
        ),
        _get(
            view="observations",
            measure="totalCost",
            aggregation="avg",
            filter=[{"column": "traceName", "operator": "=", "value": "compliance-pipeline"}],
        ),
        _get(
            view="observations",
            measure="totalTokens",
            aggregation="avg",
            filter=[{"column": "traceName", "operator": "=", "value": "compliance-pipeline"}],
        ),
        _get(
            view="scores-numeric",
            measure="value",
            aggregation="avg",
            filter=[{"column": "name", "operator": "=", "value": "escalation_decision"}],
        ),
        _get(
            view="scores-numeric",
            measure="value",
            aggregation=["avg", "p25", "p50", "p75", "p95"],
            filter=[{"column": "name", "operator": "=", "value": "risk_score"}],
        ),
        _get(
            view="scores-numeric",
            measure="value",
            aggregation="avg",
            filter=[{"column": "name", "operator": "=", "value": "pipeline_error"}],
        ),
        _get(
            view="scores-numeric",
            measure="value",
            aggregation="avg",
            filter=[{"column": "name", "operator": "=", "value": "auto_dismissed"}],
        ),
        _get(
            view="observations",
            measure="latency",
            aggregation="p95",
            dimension={"field": "name"},
            filter=[{
                "column": "name",
                "operator": "in",
                "value": ["investigador", "risk_analyzer", "decision_agent"],
            }],
        ),
    )

    def _val(r):
        row = r.data[0] if r and r.data else None
        return getattr(row, "value", None) if row else None

    risk_score_data: dict = {"avg": None, "p25": None, "p50": None, "p75": None, "p95": None}
    if r_risk and r_risk.data:
        for row in r_risk.data:
            agg = getattr(row, "aggregation", None)
            if agg in risk_score_data:
                risk_score_data[agg] = getattr(row, "value", None)

    latency_by_agent: dict = {"investigador": None, "risk_analyzer": None, "decision_agent": None}
    if r_agent_latency and r_agent_latency.data:
        for row in r_agent_latency.data:
            name = getattr(row, "dimension", None)
            if name in latency_by_agent:
                latency_by_agent[name] = getattr(row, "value", None)

    return {
        "period": {"from": from_date, "to": to_date},
        "latency_p95_ms": _val(r_latency),
        "avg_cost_per_alert_usd": _val(r_cost),
        "avg_tokens_per_alert": _val(r_tokens),
        "escalation_rate": _val(r_escalation),
        "auto_dismissed_rate": _val(r_dismissed),
        "error_rate": _val(r_error_rate),
        "risk_score": risk_score_data,
        "latency_by_agent": latency_by_agent,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "compliance-agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
