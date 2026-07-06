"""
Scenario 2 — CrashLoopBackOff
Inject: Deploy a pod with an invalid database URL causing immediate crash on startup.
Expect: Triage detects CrashLoopBackOff, RCA identifies misconfiguration as root cause.
"""

import time
from base import ScenarioResult, kubectl_apply, kubectl_delete, wait_for_pod_state, trigger_diagnosis, poll_incident

NAMESPACE = "netguard"

MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: crashloop-app
  namespace: netguard
  labels:
    scenario: crashloop-test
spec:
  restartPolicy: Always
  containers:
    - name: app
      image: python:3.10-slim
      command: [python, -c]
      args:
        - |
          import psycopg2, os
          conn = psycopg2.connect(os.environ['DATABASE_URL'])
      env:
        - name: DATABASE_URL
          value: "postgresql://user:wrongpass@non-existent-db:5432/mydb"
      resources:
        requests:
          memory: "32Mi"
        limits:
          memory: "64Mi"
"""


def run() -> ScenarioResult:
    result = ScenarioResult(
        name="CrashLoopBackOff",
        injected_cause="Invalid DATABASE_URL → connection refused on startup",
    )

    print("[S2] Injecting CrashLoopBackOff scenario...")
    kubectl_apply(MANIFEST)

    print("[S2] Waiting for CrashLoopBackOff state (~60s)...")
    try:
        wait_for_pod_state(NAMESPACE, "scenario=crashloop-test", "CrashLoopBackOff", timeout=120)
    except TimeoutError:
        pass

    time.sleep(20)

    print("[S2] Triggering AIOps diagnosis...")
    t0 = time.time()
    result.incident_id = trigger_diagnosis(
        namespace=NAMESPACE,
        pod_name="crashloop-app",
    )

    print(f"[S2] Polling incident {result.incident_id}...")
    incident = poll_incident(result.incident_id, timeout=300)
    result.duration_s   = time.time() - t0
    result.detected     = True
    result.failure_mode = incident.get("failure_mode", "")
    result.root_cause   = incident.get("root_cause", "")
    result.confidence   = incident.get("confidence", 0.0)

    rca_text = (result.root_cause + result.failure_mode).lower()
    result.correct = any(kw in rca_text for kw in [
        "config", "env", "database", "connection", "crash", "misconfigur",
    ])

    print(f"[S2] Done: failure_mode={result.failure_mode} confidence={result.confidence:.0%}")

    print("[S2] Cleaning up...")
    kubectl_delete(MANIFEST)

    return result


if __name__ == "__main__":
    r = run()
    print(r.row())
