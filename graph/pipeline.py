import uuid

from langgraph.graph import StateGraph, END

from graph.state import ComplianceState
from agents.research import ResearchAgent
from agents.risk_analyzer import RiskAnalyzerAgent
from agents.decision import DecisionAgent
from observability.langfuse_config import get_langfuse_handler, score_trace, flush

_research_agent = ResearchAgent()
_risk_agent = RiskAnalyzerAgent()
_decision_agent = DecisionAgent()


def _research_node(state: ComplianceState) -> ComplianceState:
    return _research_agent.run(state)


def _risk_analyzer_node(state: ComplianceState) -> ComplianceState:
    state = _risk_agent.run(state)
    if state.get("risk_score", 0) >= 9:
        state["decision"] = "escalate"
        state["confidence"] = 1.0
        state["reasoning_steps"] = ["Risk score ≥ 9: auto-escalated without decision agent"]
        state["decision_status"] = "done"
        state["decision_error"] = None
    return state


def _decision_node(state: ComplianceState) -> ComplianceState:
    return _decision_agent.run(state)


def _route_after_risk(state: ComplianceState) -> str:
    if state.get("risk_score", 0) >= 9:
        return END
    return "decision"


def build_pipeline():
    graph = StateGraph(ComplianceState)

    graph.add_node("research", _research_node)
    graph.add_node("risk_analyzer", _risk_analyzer_node)
    graph.add_node("decision_agent", _decision_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "risk_analyzer")
    graph.add_conditional_edges("risk_analyzer", _route_after_risk, {"decision": "decision_agent", END: END})
    graph.add_edge("decision_agent", END)

    return graph.compile()


def run_pipeline(alert: dict) -> ComplianceState:
    trace_id = str(uuid.uuid4()).replace("-", "")
    handler = get_langfuse_handler(trace_id, session_id=alert["alert_id"])
    pipeline = build_pipeline()
    try:
        state = pipeline.invoke(
            {"alert": alert, "trace_id": trace_id},
            config={
                "callbacks": [handler],
                "run_name": "compliance-pipeline",
                "metadata": {"langfuse_session_id": alert["alert_id"]},
            },
        )
        state["trace_id"] = trace_id
        score_trace(trace_id, "pipeline_error", 0.0)
        return state
    except Exception:
        score_trace(trace_id, "pipeline_error", 1.0)
        raise
    finally:
        flush()
