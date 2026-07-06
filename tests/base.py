"""
Shared helpers for AIOps evaluation scenarios.
Each scenario: inject failure → wait → trigger pipeline → poll until done → assert → cleanup.
"""

import json
import subprocess
import time
import httpx

BACKEND_URL = "https://netguard.cluster.lan"
KUBECTL     = ["kubectl"]


def kubectl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([*KUBECTL, *args], capture_output=True, text=True, check=True)


def kubectl_apply(manifest: str) -> None:
    subprocess.run(
        [*KUBECTL, "apply", "-f", "-"],
        input=manifest, text=True, capture_output=True, check=True,
    )


def kubectl_delete(manifest: str) -> None:
    subprocess.run(
        [*KUBECTL, "delete", "-f", "-", "--ignore-not-found"],
        input=manifest, text=True, capture_output=True,
    )


def _incident_ids(client: httpx.Client, trigger_source: str) -> set:
    """IDs of incidents created via the given trigger source (newest 50)."""
    resp = client.get(f"{BACKEND_URL}/api/incidents", params={"limit": 50})
    if resp.status_code != 200:
        return set()
    return {
        inc["id"] for inc in resp.json()
        if inc.get("trigger_source") == trigger_source and inc.get("id")
    }


def trigger_diagnosis(namespace: str, pod_name: str, trigger_source: str = "evaluation") -> str:
    """Fire /api/aiops/analyze and resolve the incident id it creates.

    The endpoint runs the pipeline in the background and returns
    {"status": "started"} with no id, so we diff the incident list before and
    after the trigger (filtered to our own trigger_source) to find the new one.
    This is clock-skew-proof and ignores incidents the collector raises for the
    same failing pod.
    """
    with httpx.Client(timeout=10, verify=False, follow_redirects=True) as c:
        before = _incident_ids(c, trigger_source)
        r = c.post(f"{BACKEND_URL}/api/aiops/analyze", json={
            "namespace":      namespace,
            "pod_name":       pod_name,
            "trigger_source": trigger_source,
        })
        r.raise_for_status()
        deadline = time.time() + 60
        while time.time() < deadline:
            new = _incident_ids(c, trigger_source) - before
            if new:
                return new.pop()
            time.sleep(3)
    raise TimeoutError(f"No incident appeared for pod '{pod_name}' within 60s")


def poll_incident(incident_id: str, timeout: int = 300) -> dict:
    """Poll GET /api/incidents/{id} until status != ANALYZING."""
    deadline = time.time() + timeout
    with httpx.Client(timeout=10, verify=False, follow_redirects=True) as c:
        while time.time() < deadline:
            r = c.get(f"{BACKEND_URL}/api/incidents/{incident_id}")
            if r.status_code == 200:
                data = r.json()
                if data.get("status") not in ("ANALYZING", None):
                    return data
            time.sleep(5)
    raise TimeoutError(f"Incident {incident_id} did not complete within {timeout}s")


def wait_for_pod_state(namespace: str, label: str, state: str, timeout: int = 120) -> None:
    """Wait until at least one pod matching label reaches the desired state substring."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            [*KUBECTL, "get", "pods", "-n", namespace, "-l", label,
             "--no-headers", "-o", "custom-columns=STATUS:.status.phase,COND:.status.containerStatuses[0].state"],
            capture_output=True, text=True,
        )
        if state.lower() in result.stdout.lower():
            return
        time.sleep(5)
    raise TimeoutError(f"Pod {label} did not reach state '{state}' within {timeout}s")


class ScenarioResult:
    def __init__(self, name: str, injected_cause: str):
        self.name          = name
        self.injected_cause = injected_cause
        self.incident_id   = ""
        self.detected      = False
        self.correct       = False
        self.confidence    = 0.0
        self.duration_s    = 0.0
        self.root_cause    = ""
        self.failure_mode  = ""

    def row(self) -> str:
        detected_str  = "✅" if self.detected  else "❌"
        correct_str   = "✅" if self.correct   else "❌"
        return (
            f"{self.name:<30} {self.injected_cause:<35} "
            f"{detected_str}        {correct_str}       "
            f"{self.confidence*100:>4.0f}%   {self.duration_s:>6.1f}s"
        )
