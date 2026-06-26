"""
Triage Agent — determines what broke, where, and when.

Deterministic collector: Python gathers the cluster signals directly (unhealthy
pods, recent Warning events, node status), then a single LLM call classifies the
incident scope. No agentic tool loop — the queries to run for triage are always
the same three, so the LLM only does the reasoning, not the tool selection.

Outputs a structured incident scope passed to the Evidence Agent.
"""

import json

from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm
from ..tools.kubernetes import (
    list_unhealthy_pods,
    get_k8s_events,
    get_node_status,
)


TRIAGE_SYSTEM_PROMPT = """You are a Kubernetes SRE performing incident triage.
You are given cluster signals that have ALREADY been collected: the list of
unhealthy pods, recent Warning events, and per-node status. Your job is to read
those signals and identify what broke, in which namespace, with what failure
mode, and at what time.

Return ONLY a JSON object with these exact fields:
{{
  "affected_pods": ["pod-name"],
  "affected_namespace": "namespace",
  "failure_mode": "OOMKilled|CrashLoopBackOff|Pending|Evicted|NodeNotReady|Unknown",
  "restart_count": 0,
  "first_failure_time": "ISO timestamp or unknown",
  "affected_node": "node-name or unknown",
  "severity": "HIGH|MED|LOW",
  "is_noise": false,
  "summary": "one sentence describing the incident"
}}

Rules:
- Base every field on the provided signals. Never invent pod or node names.
- If the unhealthy-pods signal shows no failing pods (e.g. "all pods healthy"),
  set is_noise to true and severity to LOW.
- failure_mode must be exactly one of the listed values.
- Be concise. Do not output anything outside the JSON object."""


def _collect_signals(trigger: dict) -> dict:
    """Run the fixed set of triage queries and return a signals bundle."""
    namespace = trigger.get("namespace") or None
    unhealthy = list_unhealthy_pods(namespace)

    # Decide which namespace to pull Warning events from: the explicit hint,
    # otherwise the namespace of the first unhealthy pod we found.
    ns_for_events = namespace
    if not ns_for_events:
        for pod in unhealthy:
            if isinstance(pod, dict) and pod.get("namespace"):
                ns_for_events = pod["namespace"]
                break

    events = get_k8s_events(ns_for_events) if ns_for_events else []
    nodes = get_node_status()

    return {
        "unhealthy_pods": unhealthy,
        "warning_events": events,
        "node_status":    nodes,
    }


async def run_triage(trigger: dict) -> dict:
    """
    Run the Triage Agent given a trigger payload.
    Returns the parsed incident scope dict.
    """
    namespace = trigger.get("namespace", "")
    signals = _collect_signals(trigger)

    prompt = ChatPromptTemplate.from_messages([
        ("system", TRIAGE_SYSTEM_PROMPT),
        ("human", """Alert received: {alert_name}
Namespace hint: {namespace}
Suspected pod: {pod_hint}

COLLECTED SIGNALS:
{signals}

Determine the incident scope. Return JSON only."""),
    ])

    chain = prompt | get_llm(temperature=0, json_mode=True)

    try:
        result = await chain.ainvoke({
            "alert_name": trigger.get("alert_name", "manual trigger"),
            "namespace":  namespace or "(none — checked all namespaces)",
            "pod_hint":   trigger.get("pod_name", "(none)"),
            "signals":    json.dumps(signals, indent=2, default=str),
        })
        output = result.content
        if "```" in output:
            output = output.split("```")[1].lstrip("json").strip()
        return json.loads(output)
    except Exception as e:
        return {
            "affected_pods":       [],
            "affected_namespace":  namespace or "unknown",
            "failure_mode":        "Unknown",
            "restart_count":       0,
            "first_failure_time":  "unknown",
            "affected_node":       "unknown",
            "severity":            "LOW",
            "is_noise":            True,
            "summary":             f"Triage failed: {e}",
            "error":               str(e),
        }
