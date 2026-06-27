"""
Evidence Agent — collects corroborating signals from Loki, Prometheus, and K8s.

Deterministic collector: Python runs the diagnostic queries directly, choosing
the PromQL set by failure mode (via tools.prometheus.query_for_failure_mode),
then a single LLM call summarizes the bundle. The raw signals are attached
verbatim as raw_evidence so downstream agents reason over real data, not an
LLM's paraphrase of it.

Receives the incident scope from the Triage Agent.
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm
from ..tools.loki import query_loki_logs
from ..tools.prometheus import query_for_failure_mode
from ..tools.kubernetes import (
    get_k8s_events_for_pod,
    describe_pod,
    get_recent_deployments,
)


EVIDENCE_SYSTEM_PROMPT = """You are a Kubernetes SRE collecting incident evidence.
You are given evidence that has ALREADY been collected for the affected pod:
Loki logs, Prometheus metric series (chosen for this failure mode), Kubernetes
events, the pod's resource limits, and any recent deployments. Read it and
produce a concise structured summary.

Return ONLY a JSON object with these exact fields:
{{
  "log_summary": "what the logs reveal",
  "last_log_line": "the final log line before failure",
  "error_lines": ["key error lines"],
  "metric_findings": "what the metrics show (trends, spikes, saturation)",
  "event_timeline": [
    {{"time": "...", "type": "...", "reason": "...", "message": "..."}}
  ],
  "resource_limits": {{"memory": "...", "cpu": "..."}},
  "recent_deployment": true,
  "deployment_detail": "what changed if a recent deployment was found, else empty"
}}

Rules:
- Quote concrete values, timestamps, and log lines from the provided evidence.
- Do not invent data that is not in the evidence.
- recent_deployment must be a boolean reflecting the recent-deployments signal.
- Output nothing outside the JSON object. Do NOT echo the raw evidence back."""


async def _collect_evidence(triage_output: dict) -> dict:
    """Run the failure-mode-aware diagnostic queries and return raw signals."""
    pods = triage_output.get("affected_pods") or []
    pod  = pods[0] if pods else "unknown"
    ns   = triage_output.get("affected_namespace", "default")
    mode = triage_output.get("failure_mode", "Unknown")

    logs    = await query_loki_logs(ns, pod)
    metrics = await query_for_failure_mode(mode, pod, ns)
    events  = get_k8s_events_for_pod(ns, pod)
    pod_desc = describe_pod(ns, pod)
    deploys = get_recent_deployments(ns)

    return {
        "pod":               pod,
        "namespace":         ns,
        "failure_mode":      mode,
        "logs":              logs,
        "prometheus":        metrics,
        "k8s_events":        events,
        "pod_description":   pod_desc,
        "recent_deployments": deploys,
    }


async def run_evidence(triage_output: dict) -> dict:
    """
    Run the Evidence Agent given the Triage Agent's output.
    Returns a structured evidence bundle (LLM summary + raw_evidence).
    """
    signals = await _collect_evidence(triage_output)

    prompt = ChatPromptTemplate.from_messages([
        ("system", EVIDENCE_SYSTEM_PROMPT),
        ("human", """INCIDENT SCOPE:
{triage}

COLLECTED EVIDENCE:
{evidence}

Summarize the evidence. Return JSON only."""),
    ])

    chain = prompt | get_llm(temperature=0, json_mode=True)

    # raw_evidence is attached verbatim from the collected signals, not the LLM.
    raw_evidence = {
        "log_lines":         signals["logs"].get("lines", []),
        "prometheus_series": signals["prometheus"],
        "k8s_events":        signals["k8s_events"],
    }

    try:
        result = await chain.ainvoke({
            "triage":   json.dumps(triage_output, indent=2, default=str),
            "evidence": json.dumps(signals,       indent=2, default=str),
        })
        output = result.content
        if "```" in output:
            output = output.split("```")[1].lstrip("json").strip()
        summary = json.loads(output)
        summary["raw_evidence"] = raw_evidence
        return summary
    except Exception as e:
        return {
            "log_summary":      "Evidence summarization failed",
            "last_log_line":    signals["logs"].get("last_line", ""),
            "error_lines":      signals["logs"].get("error_lines", []),
            "metric_findings":  "",
            "event_timeline":   [],
            "resource_limits":  {},
            "recent_deployment": bool(signals["recent_deployments"]),
            "deployment_detail": "",
            "raw_evidence":     raw_evidence,
            "degraded":         True,
            "error":            str(e),
        }
