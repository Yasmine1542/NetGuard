"""Pure functions that derive dashboard stats from a list of prediction records.

Records are the inference result dicts pulled from the Redis buffer, ordered
newest-first. These functions have no I/O so they are trivially unit-tested.
"""

from __future__ import annotations

from typing import Any

Record = dict[str, Any]


def _is_attack(p: Record) -> bool:
    return bool(p.get("is_attack", p.get("prediction", 0) > 0))


def session_stats(records: list[Record]) -> dict[str, Any]:
    total = len(records)
    alerts = sum(1 for p in records if _is_attack(p))

    # records are newest-first; reverse a window to get chronological order
    throughput = 0.0
    if total >= 2:
        window = list(reversed(records[: min(60, total)]))
        elapsed = window[-1].get("timestamp", 0) - window[0].get("timestamp", 0)
        throughput = round(len(window) / elapsed, 2) if elapsed > 0 else 0.0

    latencies = [p["latency_ms"] for p in records if "latency_ms" in p]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    class_counts: dict[str, int] = {}
    for p in records:
        label = p.get("label", "Normal")
        class_counts[label] = class_counts.get(label, 0) + 1

    return {
        "predictions_total": total,
        "alerts_total": alerts,
        "alert_count": alerts,
        "alert_rate": round(alerts / total, 4) if total else 0.0,
        "throughput_per_s": throughput,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "class_counts": class_counts,
    }


def live_stats(records: list[Record]) -> dict[str, Any]:
    """Binary precision/recall/F1 over records that carry ground truth."""
    labeled = [
        (1 if _is_attack(p) else 0, 0 if p.get("true_label") in ("normal", "Normal") else 1)
        for p in records
        if p.get("true_label", "unknown") not in ("unknown", "", None)
    ]
    if not labeled:
        return {"sample_size": 0, "live": False}

    tp = sum(pred == 1 and truth == 1 for pred, truth in labeled)
    fp = sum(pred == 1 and truth == 0 for pred, truth in labeled)
    fn = sum(pred == 0 and truth == 1 for pred, truth in labeled)
    tn = sum(pred == 0 and truth == 0 for pred, truth in labeled)
    n = len(labeled)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / n if n else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "sample_size": n,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "live": True,
    }
