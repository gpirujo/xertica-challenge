import unittest
from unittest.mock import patch

from langgraph.graph import END

from graph.pipeline import (
    _decision_node,
    _research_node,
    _risk_analyzer_node,
    _route_after_risk,
)


_ALERT = {
    "alert_id": "ALT-001",
    "customer_id": "CUST-001",
    "alert_type": "structuring",
    "description": "Depósitos fraccionados bajo umbral.",
}


def _run_nodes(research_side_effect, risk_side_effect, decision_side_effect, state):
    """Execute the three nodes in pipeline order, honouring the routing branch."""
    state = _research_node(state)
    state = _risk_analyzer_node(state)
    if _route_after_risk(state) != END:
        state = _decision_node(state)
    return state


class TestPipeline(unittest.TestCase):
    def test_pipeline_runs_all_three_nodes(self):
        def research_run(s):
            return {**s, "customer": {}, "investigador_status": "done"}

        def risk_run(s):
            return {**s, "risk_score": 5, "risk_analyzer_status": "done"}

        def decision_run(s):
            return {**s, "decision": "dismiss", "decision_status": "done"}

        with patch("graph.pipeline._research_agent.run", side_effect=research_run) as mock_research, \
             patch("graph.pipeline._risk_agent.run", side_effect=risk_run) as mock_risk, \
             patch("graph.pipeline._decision_agent.run", side_effect=decision_run) as mock_decision:
            _run_nodes(research_run, risk_run, decision_run, {"alert": _ALERT})

        mock_research.assert_called_once()
        mock_risk.assert_called_once()
        mock_decision.assert_called_once()

    def test_pipeline_auto_escalates_on_high_risk(self):
        def research_run(s):
            return {**s, "customer": {}, "investigador_status": "done"}

        def risk_run(s):
            return {**s, "risk_score": 9, "risk_analyzer_status": "done"}

        with patch("graph.pipeline._research_agent.run", side_effect=research_run), \
             patch("graph.pipeline._risk_agent.run", side_effect=risk_run), \
             patch("graph.pipeline._decision_agent.run") as mock_decision:
            result = _run_nodes(research_run, risk_run, None, {"alert": _ALERT})

        mock_decision.assert_not_called()
        self.assertEqual(result["decision"], "escalate")
        self.assertAlmostEqual(result["confidence"], 1.0)

    def test_pipeline_routes_to_decision_on_low_risk(self):
        def research_run(s):
            return {**s, "customer": {}, "investigador_status": "done"}

        def risk_run(s):
            return {**s, "risk_score": 5, "risk_analyzer_status": "done"}

        def decision_run(s):
            return {**s, "decision": "dismiss", "decision_status": "done"}

        with patch("graph.pipeline._research_agent.run", side_effect=research_run), \
             patch("graph.pipeline._risk_agent.run", side_effect=risk_run), \
             patch("graph.pipeline._decision_agent.run", side_effect=decision_run) as mock_decision:
            _run_nodes(research_run, risk_run, decision_run, {"alert": _ALERT})

        mock_decision.assert_called_once()


if __name__ == "__main__":
    unittest.main()
