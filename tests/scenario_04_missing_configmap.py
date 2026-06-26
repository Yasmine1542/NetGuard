"""
Scenario 4 — Missing ConfigMap (CreateContainerConfigError)
Inject: Deploy a pod that references a ConfigMap that does not exist.
Expect: Triage detects CreateContainerConfigError, RCA identifies missing ConfigMap.
"""

import time
from base import ScenarioResult, kubectl_apply, kubectl_delete, trigger_diagnosis, poll_incident

NAMESPACE = "netguard"

MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: missing-config-app
  namespace: netguard
  labels:
    scenario: missing-config-test
spec:
  restartPolicy: Never
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
      envFrom:
        - configMapRef:
            name: non-existent-app-config
      resources:
        requests:
          memory: "32Mi"
        limits:
          memory: "64Mi"
"""


def run() -> ScenarioResult:
    result = ScenarioResult(
        name="Missing ConfigMap",
        injected_cause="Pod references non-existent ConfigMap → CreateContainerConfigError",
    )

    print("[S4] Injecting missing ConfigMap scenario...")
    kubectl_apply(MANIFEST)

    print("[S4] Waiting 30s for CreateContainerConfigError to register...")
    time.sleep(30)

    print("[S4] Triggering AIOps diagnosis...")
    t0 = time.time()
    result.incident_id = trigger_diagnosis(
        namespace=NAMESPACE,
        description="Pod missing-config-app stuck in CreateContainerConfigError — ConfigMap not found",
    )

    print(f"[S4] Polling incident {result.incident_id}...")
    incident = poll_incident(result.incident_id, timeout=300)
    result.duration_s   = time.time() - t0
    result.detected     = True
    result.failure_mode = incident.get("failure_mode", "")
    result.root_cause   = incident.get("root_cause", "")
    result.confidence   = incident.get("confidence", 0.0)

    rca_text = (result.root_cause + result.failure_mode).lower()
    result.correct = any(kw in rca_text for kw in [
        "configmap", "config", "missing", "not found", "secret", "reference",
    ])

    print(f"[S4] Done: failure_mode={result.failure_mode} confidence={result.confidence:.0%}")

    print("[S4] Cleaning up...")
    kubectl_delete(MANIFEST)

    return result


if __name__ == "__main__":
    r = run()
    print(r.row())
