"""
Prometheus query tools for the Evidence Agent.
"""

import os
import time
from typing import Optional
import httpx

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "")

# Pre-built PromQL expressions keyed by failure mode
FAILURE_QUERIES: dict[str, dict[str, str]] = {
    "OOMKilled": {
        "memory_usage":   'container_memory_working_set_bytes{{pod=~"{pod}.*", container!=""}}',
        "memory_limit":   'kube_pod_container_resource_limits{{pod=~"{pod}.*", resource="memory"}}',
        "restarts":       'kube_pod_container_status_restarts_total{{pod=~"{pod}.*"}}',
    },
    "CrashLoopBackOff": {
        "restarts":       'kube_pod_container_status_restarts_total{{pod=~"{pod}.*"}}',
        "cpu_usage":      'rate(container_cpu_usage_seconds_total{{pod=~"{pod}.*", container!=""}}[5m])',
        "memory_usage":   'container_memory_working_set_bytes{{pod=~"{pod}.*", container!=""}}',
    },
    "Pending": {
        "node_memory":    'kube_node_status_allocatable{{resource="memory"}}',
        "node_cpu":       'kube_node_status_allocatable{{resource="cpu"}}',
        "pvc_bound":      'kube_persistentvolumeclaim_status_phase{{namespace="{namespace}"}}',
    },
    "default": {
        "cpu_usage":      'rate(container_cpu_usage_seconds_total{{pod=~"{pod}.*", container!=""}}[5m])',
        "memory_usage":   'container_memory_working_set_bytes{{pod=~"{pod}.*", container!=""}}',
        "restarts":       'kube_pod_container_status_restarts_total{{pod=~"{pod}.*"}}',
        "network_rx":     'rate(container_network_receive_bytes_total{{pod=~"{pod}.*"}}[5m])',
    },
}


async def query_prometheus(
    promql: str,
    since_minutes: int = 30,
    step_seconds: int = 60,
) -> dict:
    """
    Run a PromQL range query and return a compact time series summary.
    """
    if not PROMETHEUS_URL:
        return _mock_metric(promql)

    end   = int(time.time())
    start = end - (since_minutes * 60)

    params = {
        "query": promql,
        "start": str(start),
        "end":   str(end),
        "step":  str(step_seconds),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {"error": str(e), "series": []}

    series = []
    for result in data.get("data", {}).get("result", []):
        values = [(float(ts), float(v)) for ts, v in result.get("values", [])]
        if not values:
            continue
        vals = [v for _, v in values]
        series.append({
            "metric": result.get("metric", {}),
            "min":    round(min(vals), 4),
            "max":    round(max(vals), 4),
            "latest": round(vals[-1],  4),
            "trend":  _trend(vals),
            "points": values[-10:],   # last 10 points for context
        })

    return {"query": promql, "series": series}


async def query_for_failure_mode(
    failure_mode: str,
    pod_name: str,
    namespace: str,
    since_minutes: int = 30,
) -> dict:
    """
    Run the standard set of PromQL queries for a given failure mode.
    Returns a dict of metric_name → query result.
    """
    queries = FAILURE_QUERIES.get(failure_mode, FAILURE_QUERIES["default"])
    results = {}

    for metric_name, template in queries.items():
        promql = template.format(pod=pod_name, namespace=namespace)
        results[metric_name] = await query_prometheus(promql, since_minutes)

    return results


def _trend(values: list[float]) -> str:
    if len(values) < 3:
        return "stable"
    first_third = sum(values[:len(values)//3]) / (len(values)//3)
    last_third  = sum(values[-(len(values)//3):]) / (len(values)//3)
    ratio = last_third / first_third if first_third > 0 else 1.0
    if ratio > 1.5:
        return "rising"
    if ratio < 0.7:
        return "falling"
    return "stable"


def _mock_metric(promql: str) -> dict:
    now = int(time.time())
    # Rising memory trend climbing toward the 512Mi limit (536870912 bytes).
    points = [(now - (29 - i) * 60, 300_000_000 + i * 8_000_000) for i in range(30)]
    return {
        "query": promql,
        "series": [{
            "metric": {"pod": "inference-7d9c8b6f4-q4n2x", "container": "inference"},
            "min":    300_000_000,
            "max":    points[-1][1],
            "latest": points[-1][1],
            "trend":  "rising",
            "points": points[-10:],
        }],
    }
