"""
Library module for fetching pipeline metrics from Langfuse.
Callers are responsible for loading environment variables before calling get_metrics.
"""
import json
import sys
from datetime import datetime, timedelta


def _fetch(lf, from_ts, to_ts, view, measure, aggregation, filter_name, filter_value, dimensions=None):
    q = {
        "view": view,
        "metrics": [{"measure": measure, "aggregation": aggregation}],
        "dimensions": dimensions or [],
        "filters": [{"column": "name", "operator": "=", "value": filter_value, "type": "string"}],
        "fromTimestamp": from_ts,
        "toTimestamp": to_ts,
    }
    try:
        r = lf.api.metrics.metrics(query=json.dumps(q))
        row = r.data[0] if r and r.data else None
        if row is None:
            return None
        return row.get(f"{aggregation}_{measure}")
    except Exception as e:
        print(f"  [warn] {view}/{measure}/{aggregation}: {e}", file=sys.stderr)
        return None


def _fetch_by_agent(lf, from_ts, to_ts):
    q = {
        "view": "observations",
        "metrics": [{"measure": "latency", "aggregation": "p95"}],
        "dimensions": [{"field": "name"}],
        "filters": [{"column": "name", "operator": "any of", "value": ["research", "risk_analyzer", "decision_agent"], "type": "stringOptions"}],
        "fromTimestamp": from_ts,
        "toTimestamp": to_ts,
    }
    try:
        r = lf.api.metrics.metrics(query=json.dumps(q))
        result = {"research": None, "risk_analyzer": None, "decision_agent": None}
        if r and r.data:
            for row in r.data:
                name = row.get("name") or row.get("dimension")
                if name in result:
                    result[name] = row.get("p95_latency")
        return result
    except Exception as e:
        print(f"  [warn] latency_by_agent: {e}", file=sys.stderr)
        return {"research": None, "risk_analyzer": None, "decision_agent": None}


def _fetch_count(lf, from_ts, to_ts):
    q = {
        "view": "observations",
        "metrics": [{"measure": "count", "aggregation": "count"}],
        "dimensions": [],
        "filters": [{"column": "name", "operator": "=", "value": "compliance-pipeline", "type": "string"}],
        "fromTimestamp": from_ts,
        "toTimestamp": to_ts,
    }
    try:
        r = lf.api.metrics.metrics(query=json.dumps(q))
        row = r.data[0] if r and r.data else None
        return int(row["count_count"]) if row and "count_count" in row else None
    except Exception as e:
        print(f"  [warn] count: {e}", file=sys.stderr)
        return None


def get_metrics(from_date: str | None, to_date: str | None) -> dict:
    from langfuse import get_client
    lf = get_client()

    now = datetime.utcnow()
    to_date = to_date or now.date().isoformat()
    from_date = from_date or (now - timedelta(days=30)).date().isoformat()
    from_ts = f"{from_date}T00:00:00Z"
    to_ts = f"{to_date}T23:59:59Z"

    queries = [
        ("latency_p95_ms",          "observations",   "latency",    "p95", "name", "compliance-pipeline"),
        ("avg_cost_per_alert_usd",   "observations",   "totalCost",  "avg", "name", "ChatOpenAI"),
        ("avg_tokens_per_alert",     "observations",   "totalTokens","avg", "name", "ChatOpenAI"),
        ("escalation_rate",          "scores-numeric", "value",      "avg", "name", "escalation_decision"),
        ("avg_confidence",           "scores-numeric", "value",      "avg", "name", "confidence"),
        ("auto_dismissed_rate",      "scores-numeric", "value",      "avg", "name", "auto_dismissed"),
        ("error_rate",               "scores-numeric", "value",      "avg", "name", "pipeline_error"),
        ("risk_score_avg",           "scores-numeric", "value",      "avg", "name", "risk_score"),
        ("risk_score_p50",           "scores-numeric", "value",      "p50", "name", "risk_score"),
        ("risk_score_p95",           "scores-numeric", "value",      "p95", "name", "risk_score"),
    ]

    report = {"period": {"from": from_date, "to": to_date}}

    for key, view, measure, agg, filter_col, filter_val in queries:
        print(f"  [{key}] iniciando...", file=sys.stderr, flush=True)
        report[key] = _fetch(lf, from_ts, to_ts, view, measure, agg, filter_col, filter_val)
        print(f"  [{key}] ok: {report[key]}", file=sys.stderr, flush=True)

    print("  fetching latency_by_agent...", file=sys.stderr, flush=True)
    report["latency_by_agent"] = _fetch_by_agent(lf, from_ts, to_ts)
    print(f"  latency_by_agent ok: {report['latency_by_agent']}", file=sys.stderr, flush=True)

    print("  fetching total_traces...", file=sys.stderr, flush=True)
    report["total_traces"] = _fetch_count(lf, from_ts, to_ts)
    print(f"  total_traces ok: {report['total_traces']}", file=sys.stderr, flush=True)

    return report
