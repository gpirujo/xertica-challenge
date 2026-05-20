import os

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



@app.get("/health")
async def health():
    return {"status": "ok", "service": "compliance-agent"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
