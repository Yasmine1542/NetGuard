"""
AIOps Evaluation — runs all 4 scenarios sequentially and prints a results table.

Usage:
    cd tests
    python run_evaluation.py

Prerequisites:
    - NetGuard backend reachable at http://netguard.cluster.lan
    - aiops-engine deployed (Groq-backed); /api/aiops and /api/incidents reachable
    - kubectl configured and pointing at the cluster
"""

import importlib
import time
from base import ScenarioResult

SCENARIOS = [
    "scenario_01_oom",
    "scenario_02_crashloop",
    "scenario_03_pending",
    "scenario_04_missing_configmap",
]

HEADER = (
    f"\n{'Scenario':<30} {'Injected Cause':<35} "
    f"{'Detected':<9} {'Correct':<8} {'Conf':>5}   {'Time':>7}\n"
    + "─" * 100
)


def main() -> None:
    print("=" * 100)
    print("  NetGuard AIOps Evaluation Suite — 4-Agent LangChain Pipeline")
    print("=" * 100)

    results: list[ScenarioResult] = []

    for mod_name in SCENARIOS:
        print(f"\n{'─'*60}")
        print(f"  Running: {mod_name}")
        print(f"{'─'*60}")
        try:
            mod = importlib.import_module(mod_name)
            r   = mod.run()
            results.append(r)
        except Exception as e:
            print(f"  ERROR: {e}")
            dummy              = ScenarioResult(mod_name, "error")
            dummy.detected     = False
            dummy.correct      = False
            results.append(dummy)

        time.sleep(10)  # brief pause between scenarios

    # ── Print results table ───────────────────────────────────────────
    print("\n" + "=" * 100)
    print("  EVALUATION RESULTS")
    print("=" * 100)
    print(HEADER)
    for r in results:
        print(r.row())
    print("─" * 100)

    total     = len(results)
    detected  = sum(1 for r in results if r.detected)
    correct   = sum(1 for r in results if r.correct)
    avg_conf  = sum(r.confidence for r in results if r.detected) / max(detected, 1)
    avg_time  = sum(r.duration_s for r in results if r.detected) / max(detected, 1)

    print(
        f"\n  Detection rate : {detected}/{total}  ({detected/total*100:.0f}%)\n"
        f"  Accuracy       : {correct}/{total}  ({correct/total*100:.0f}%)\n"
        f"  Avg confidence : {avg_conf*100:.1f}%\n"
        f"  Avg time-to-RCA: {avg_time:.1f}s\n"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()
