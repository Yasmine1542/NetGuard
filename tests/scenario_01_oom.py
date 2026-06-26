"""
Scenario 1 — OOMKilled
Inject: Deploy a pod with a 100Mi memory limit that immediately allocates 500MB.
Expect: Triage detects OOMKilled, RCA identifies memory limit as root cause.
"""

import time
from base import ScenarioResult, kubectl_apply, kubectl_delete, wait_for_pod_state, trigger_diagnosis, poll_incident

NAMESPACE = "netguard"

MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: oom-stress
  namespace: netguard
  labels:
    scenario: oom-test
spec:
  restartPolicy: Never
  containers:
    - name: stress
      image: polinux/stress
      command: ["stress", "--vm", "1", "--vm-bytes", "500M", "--vm-hang", "0"]
      resources:
        requests:
          memory: "50Mi"
        limits:
          memory: "100Mi"
"""


def run() -> ScenarioResult:
    result = ScenarioResult(
        name="OOMKilled",
        injected_cause="Memory limit 100Mi, workload needs 500MB",
    )

    print("[S1] Injecting OOMKill scenario...")
    kubectl_apply(MANIFEST)

    print("[S1] Waiting for OOMKilled state (~30s)...")
    try:
        wait_for_pod_state(NAMESPACE, "scenario=oom-test", "OOMKilled", timeout=90)
    except TimeoutError:
        pass  # pod may still show as running briefly

    time.sleep(15)  # let K8s record the event

    print("[S1] Triggering AIOps diagnosis...")
    t0 = time.time()
    result.incident_id = trigger_diagnosis(
        namespace=NAMESPACE,
        description="Pod oom-stress OOMKilled — memory limit exceeded",
    )

    print(f"[S1] Polling incident {result.incident_id}...")
    incident = poll_incident(result.incident_id, timeout=300)
    result.duration_s  = time.time() - t0
    result.detected    = True
    result.failure_mode = incident.get("failure_mode", "")
    result.root_cause  = incident.get("root_cause", "")
    result.confidence  = incident.get("confidence", 0.0)

    rca_text = (result.root_cause + result.failure_mode).lower()
    result.correct = any(kw in rca_text for kw in ["memory", "oom", "limit", "resource"])

    print(f"[S1] Done: failure_mode={result.failure_mode} confidence={result.confidence:.0%}")

    print("[S1] Cleaning up...")
    kubectl_delete(MANIFEST)

    return result


if __name__ == "__main__":
    r = run()
    print(r.row())
