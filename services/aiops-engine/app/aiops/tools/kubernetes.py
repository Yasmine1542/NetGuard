"""
Kubernetes API tools for the Triage and Evidence agents.
Uses the kubernetes Python client — no subprocess/kubectl calls.
Falls back to mock data when running outside a cluster (local dev).
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

IN_CLUSTER = os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token")

try:
    from kubernetes import client, config
    if IN_CLUSTER:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    _v1   = client.CoreV1Api()
    _apps = client.AppsV1Api()
    K8S_AVAILABLE = True
except Exception:
    K8S_AVAILABLE = False


def _since_dt(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def list_unhealthy_pods(namespace: Optional[str] = None) -> list[dict]:
    """Return pods not in Running or Completed/Succeeded phase."""
    if not K8S_AVAILABLE:
        return _mock_unhealthy_pods()

    ns = namespace or ""
    try:
        if ns:
            pods = _v1.list_namespaced_pod(ns).items
        else:
            pods = _v1.list_pod_for_all_namespaces().items
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    for pod in pods:
        phase = pod.status.phase or "Unknown"
        if phase in ("Running", "Succeeded"):
            # Check for containers in bad state even if pod phase is Running
            bad = []
            for cs in (pod.status.container_statuses or []):
                if cs.state.waiting and cs.state.waiting.reason in (
                    "CrashLoopBackOff", "OOMKilled", "Error", "ImagePullBackOff"
                ):
                    bad.append({
                        "container": cs.name,
                        "reason": cs.state.waiting.reason,
                        "restarts": cs.restart_count,
                    })
            if not bad:
                continue
            failure_mode = bad[0]["reason"]
            restarts = bad[0]["restarts"]
        else:
            failure_mode = phase
            restarts = sum(
                (cs.restart_count for cs in (pod.status.container_statuses or [])), 0
            )

        results.append({
            "name":         pod.metadata.name,
            "namespace":    pod.metadata.namespace,
            "phase":        phase,
            "failure_mode": failure_mode,
            "restarts":     restarts,
            "node":         pod.spec.node_name,
            "start_time":   pod.status.start_time.isoformat() if pod.status.start_time else None,
        })

    return results or [{"status": "all pods healthy"}]


def get_k8s_events(namespace: str, since_minutes: int = 10) -> list[dict]:
    """Return Warning events from a namespace in the last N minutes."""
    if not K8S_AVAILABLE:
        return _mock_events()

    try:
        events = _v1.list_namespaced_event(namespace).items
    except Exception as e:
        return [{"error": str(e)}]

    cutoff = _since_dt(since_minutes)
    results = []
    for e in events:
        if e.type != "Warning":
            continue
        ts = e.last_timestamp or e.event_time
        if ts and ts.replace(tzinfo=timezone.utc) < cutoff:
            continue
        results.append({
            "time":    ts.isoformat() if ts else "unknown",
            "type":    e.type,
            "reason":  e.reason,
            "object":  f"{e.involved_object.kind}/{e.involved_object.name}",
            "message": e.message,
            "count":   e.count,
        })

    return sorted(results, key=lambda x: x["time"]) or [{"status": "no warning events"}]


def get_k8s_events_for_pod(namespace: str, pod_name: str, since_minutes: int = 30) -> list[dict]:
    """Return all events (any type) for a specific pod."""
    if not K8S_AVAILABLE:
        return _mock_events()

    try:
        events = _v1.list_namespaced_event(
            namespace,
            field_selector=f"involvedObject.name={pod_name}",
        ).items
    except Exception as e:
        return [{"error": str(e)}]

    cutoff = _since_dt(since_minutes)
    results = []
    for e in events:
        ts = e.last_timestamp or e.event_time
        if ts and ts.replace(tzinfo=timezone.utc) < cutoff:
            continue
        results.append({
            "time":    ts.isoformat() if ts else "unknown",
            "type":    e.type,
            "reason":  e.reason,
            "message": e.message,
            "count":   e.count,
        })

    return sorted(results, key=lambda x: x["time"])


def describe_pod(namespace: str, pod_name: str) -> dict:
    """Return resource limits, requests, image, and conditions for a pod."""
    if not K8S_AVAILABLE:
        return _mock_describe_pod()

    try:
        pod = _v1.read_namespaced_pod(pod_name, namespace)
    except Exception as e:
        return {"error": str(e)}

    containers = []
    for c in pod.spec.containers:
        limits   = {}
        requests = {}
        if c.resources:
            limits   = {k: v for k, v in (c.resources.limits   or {}).items()}
            requests = {k: v for k, v in (c.resources.requests or {}).items()}
        containers.append({
            "name":     c.name,
            "image":    c.image,
            "limits":   limits,
            "requests": requests,
        })

    restart_count = sum(
        cs.restart_count for cs in (pod.status.container_statuses or [])
    )

    conditions = [
        {"type": c.type, "status": c.status, "reason": c.reason}
        for c in (pod.status.conditions or [])
    ]

    return {
        "name":          pod.metadata.name,
        "namespace":     pod.metadata.namespace,
        "node":          pod.spec.node_name,
        "phase":         pod.status.phase,
        "restart_count": restart_count,
        "containers":    containers,
        "conditions":    conditions,
        "start_time":    pod.status.start_time.isoformat() if pod.status.start_time else None,
    }


def get_node_status() -> list[dict]:
    """Return Ready/NotReady status and pressure conditions for all nodes."""
    if not K8S_AVAILABLE:
        return _mock_nodes()

    try:
        nodes = _v1.list_node().items
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    for node in nodes:
        conditions = {c.type: c.status for c in (node.status.conditions or [])}
        results.append({
            "name":            node.metadata.name,
            "ready":           conditions.get("Ready") == "True",
            "memory_pressure": conditions.get("MemoryPressure") == "True",
            "disk_pressure":   conditions.get("DiskPressure") == "True",
            "pid_pressure":    conditions.get("PIDPressure") == "True",
            "allocatable":     dict(node.status.allocatable or {}),
        })

    return results


def get_recent_deployments(namespace: str, since_hours: int = 2) -> list[dict]:
    """Return deployments that were updated in the last N hours."""
    if not K8S_AVAILABLE:
        return []

    try:
        deps = _apps.list_namespaced_deployment(namespace).items
    except Exception as e:
        return [{"error": str(e)}]

    cutoff = _since_dt(since_hours * 60)
    results = []
    for d in deps:
        ts = d.metadata.creation_timestamp
        if not ts:
            continue
        if ts.replace(tzinfo=timezone.utc) < cutoff:
            continue
        results.append({
            "name":           d.metadata.name,
            "namespace":      d.metadata.namespace,
            "updated_at":     ts.isoformat(),
            "ready_replicas": d.status.ready_replicas or 0,
            "replicas":       d.spec.replicas or 0,
        })

    return results


def get_cluster_summary() -> dict:
    """Real cluster snapshot for the dashboard: counts plus per-node and
    per-namespace detail. Uses the in-cluster client (RBAC granted on nodes +
    pods). Namespace breakdown is derived from the pod list, so no separate
    namespaces permission is needed."""
    if not K8S_AVAILABLE:
        return _mock_cluster_summary()

    try:
        nodes = _v1.list_node().items
        pods  = _v1.list_pod_for_all_namespaces().items
    except Exception as e:
        return {"error": str(e)}

    node_list = []
    nodes_ready = 0
    for n in nodes:
        ready = any(c.type == "Ready" and c.status == "True" for c in (n.status.conditions or []))
        if ready:
            nodes_ready += 1
        addrs  = {a.type: a.address for a in (n.status.addresses or [])}
        labels = n.metadata.labels or {}
        is_cp  = ("node-role.kubernetes.io/control-plane" in labels
                  or "node-role.kubernetes.io/master" in labels)
        node_list.append({
            "name":    n.metadata.name,
            "ip":      addrs.get("InternalIP", "—"),
            "role":    "control-plane" if is_cp else "worker",
            "version": n.status.node_info.kubelet_version if n.status.node_info else "—",
            "ready":   ready,
        })

    pods_running   = sum(1 for p in pods if p.status.phase == "Running")
    pods_unhealthy = sum(1 for p in pods if p.status.phase not in ("Running", "Succeeded"))

    ns_counts: dict[str, int] = {}
    for p in pods:
        ns_counts[p.metadata.namespace] = ns_counts.get(p.metadata.namespace, 0) + 1
    ns_list = [{"name": k, "pods": v} for k, v in sorted(ns_counts.items())]

    return {
        "nodes_total":    len(nodes),
        "nodes_ready":    nodes_ready,
        "pods_total":     len(pods),
        "pods_running":   pods_running,
        "pods_unhealthy": pods_unhealthy,
        "namespaces":     len(ns_counts),
        "nodes":          node_list,
        "namespace_pods": ns_list,
        "data_source":    "live",
    }


def data_source() -> str:
    """'live' when reading the real cluster, 'mock' when serving demo fallback
    data off-cluster — surfaced so a misconfigured deployment never passes mock
    data off as real."""
    return "live" if K8S_AVAILABLE else "mock"


# ── Mock data for local dev (no cluster) ─────────────────────────────────────
# A coherent NetGuard demo incident: the inference pod is OOMKilled because a
# deploy lowered its memory limit below what the LightGBM model needs under load.

_DEMO_POD = "inference-7d9c8b6f4-q4n2x"
_DEMO_NS = "netguard"
_DEMO_NODE = "worker2-yt"


def _mock_cluster_summary() -> dict:
    return {
        "nodes_total": 4, "nodes_ready": 4,
        "pods_total": 31, "pods_running": 30, "pods_unhealthy": 1,
        "namespaces": 6,
        "nodes": [
            {"name": "master-yt",  "ip": "192.168.50.10", "role": "control-plane", "version": "v1.29.0", "ready": True},
            {"name": "worker1-yt", "ip": "192.168.50.20", "role": "worker", "version": "v1.29.0", "ready": True},
            {"name": "worker2-yt", "ip": "192.168.50.22", "role": "worker", "version": "v1.29.0", "ready": True},
            {"name": "worker3-yt", "ip": "192.168.50.23", "role": "worker", "version": "v1.29.0", "ready": True},
        ],
        "namespace_pods": [
            {"name": "argocd", "pods": 7},
            {"name": "monitoring", "pods": 9},
            {"name": "netguard", "pods": 6},
        ],
        "data_source": "mock",
    }


def _mock_unhealthy_pods() -> list[dict]:
    return [
        {
            "name":         _DEMO_POD,
            "namespace":    _DEMO_NS,
            "phase":        "Running",
            "failure_mode": "OOMKilled",
            "restarts":     6,
            "node":         _DEMO_NODE,
            "start_time":   "2026-06-25T09:12:31Z",
        }
    ]


def _mock_events() -> list[dict]:
    return [
        {"time": "2026-06-25T09:14:20Z", "type": "Warning", "reason": "OOMKilling",
         "object": f"Pod/{_DEMO_POD}",
         "message": "Memory cgroup out of memory: killed process (python) in container inference", "count": 6},
        {"time": "2026-06-25T09:14:22Z", "type": "Warning", "reason": "BackOff",
         "object": f"Pod/{_DEMO_POD}",
         "message": "Back-off restarting failed container inference", "count": 11},
    ]


def _mock_describe_pod() -> dict:
    return {
        "name":          _DEMO_POD,
        "namespace":     _DEMO_NS,
        "node":          _DEMO_NODE,
        "phase":         "Running",
        "restart_count": 6,
        "containers":    [{"name": "inference", "image": "192.168.50.10:5000/netguard/inference:1.4.0",
                           "limits": {"memory": "512Mi", "cpu": "1000m"},
                           "requests": {"memory": "256Mi", "cpu": "100m"}}],
        "conditions":    [{"type": "Ready", "status": "False", "reason": "ContainersNotReady"}],
        "start_time":    "2026-06-25T09:12:31Z",
    }


def _mock_nodes() -> list[dict]:
    return [
        {"name": "master-yt",  "ready": True, "memory_pressure": False, "disk_pressure": False, "pid_pressure": False, "allocatable": {"cpu": "8", "memory": "16Gi"}},
        {"name": "worker1-yt", "ready": True, "memory_pressure": False, "disk_pressure": False, "pid_pressure": False, "allocatable": {"cpu": "4", "memory": "8Gi"}},
        {"name": "worker2-yt", "ready": True, "memory_pressure": True,  "disk_pressure": False, "pid_pressure": False, "allocatable": {"cpu": "4", "memory": "8Gi"}},
        {"name": "worker3-yt", "ready": True, "memory_pressure": False, "disk_pressure": False, "pid_pressure": False, "allocatable": {"cpu": "4", "memory": "8Gi"}},
    ]
