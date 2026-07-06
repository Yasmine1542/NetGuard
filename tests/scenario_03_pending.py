"""
Scenario 3 — Pod stuck Pending
Inject: Deploy a pod requesting 64 CPU cores — unschedulable on any node.
Expect: Triage detects Pending, RCA identifies insufficient cluster resources.
"""

import time
from base import ScenarioResult, kubectl_apply, kubectl_delete, trigger_diagnosis, poll_incident

NAMESPACE = "netguard"

MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: pending-overcommit
  namespace: netguard
  labels:
    scenario: pending-test
spec:
  restartPolicy: Never
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      resources:
        requests:
          cpu: "64"
          memory: "128Gi"
        limits:
          cpu: "64"
          memory: "128Gi"
"""


def run() -> ScenarioResult:
    result = ScenarioResult(
        name="Pod Pending (Unschedulable)",
        injected_cause="Requests 64 CPU / 128Gi — no node can satisfy",
    )

    print("[S3] Injecting unschedulable pod...")
    kubectl_apply(MANIFEST)

    print("[S3] Waiting 30s for Pending state to register...")
    time.sleep(30)

    print("[S3] Triggering AIOps diagnosis...")
    t0 = time.time()
    result.incident_id = trigger_diagnosis(
        namespace=NAMESPACE,
        pod_name="pending-overcommit",
    )

    print(f"[S3] Polling incident {result.incident_id}...")
    incident = poll_incident(result.incident_id, timeout=300)
    result.duration_s   = time.time() - t0
    result.detected     = True
    result.failure_mode = incident.get("failure_mode", "")
    result.root_cause   = incident.get("root_cause", "")
    result.confidence   = incident.get("confidence", 0.0)

    rca_text = (result.root_cause + result.failure_mode).lower()
    result.correct = any(kw in rca_text for kw in [
        "resource", "cpu", "memory", "schedul", "pending", "insufficient", "capacity",
    ])

    print(f"[S3] Done: failure_mode={result.failure_mode} confidence={result.confidence:.0%}")

    print("[S3] Cleaning up...")
    kubectl_delete(MANIFEST)

    return result


if __name__ == "__main__":
    r = run()
    print(r.row())
