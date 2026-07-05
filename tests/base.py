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


def trigger_diagnosis(namespace: str, description: str) -> str:
    """POST to /api/aiops/analyze and return the incident_id."""
    with httpx.Client(timeout=10, verify=False, follow_redirects=True) as c:
        r = c.post(f"{BACKEND_URL}/api/aiops/analyze", json={
            "namespace":   namespace,
            "description": description,
            "source":      "evaluation-script",
        })
        r.raise_for_status()
        return r.json()["incident_id"]


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
