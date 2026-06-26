"""Unit tests for the pure metrics functions."""

from app.metrics import live_stats, session_stats


def _rec(is_attack, label, true_label, latency, ts):
    return {
        "is_attack": is_attack,
        "label": label,
        "true_label": true_label,
        "latency_ms": latency,
        "timestamp": ts,
    }


# Newest-first, as returned by the Redis buffer (LPUSH order).
RECORDS = [
    _rec(True, "DoS", "neptune", 4.0, 30),
    _rec(False, "Normal", "normal", 2.0, 28),
    _rec(True, "Probe", "normal", 6.0, 26),
    _rec(False, "Normal", "neptune", 3.0, 24),
]


def test_session_stats_counts_and_rates():
    s = session_stats(RECORDS)
    assert s["predictions_total"] == 4
    assert s["alerts_total"] == 2
    assert s["alert_rate"] == 0.5
    assert s["class_counts"]["Normal"] == 2
    assert s["avg_latency_ms"] == 3.75


def test_session_stats_handles_empty():
    s = session_stats([])
    assert s["predictions_total"] == 0
    assert s["alert_rate"] == 0.0


def test_live_stats_confusion_matrix():
    s = live_stats(RECORDS)
    # TP: rec0 (attack/attack); FP: rec2 (attack/normal); FN: rec3 (normal/attack); TN: rec1
    assert s["true_positives"] == 1
    assert s["false_positives"] == 1
    assert s["false_negatives"] == 1
    assert s["true_negatives"] == 1
    assert s["sample_size"] == 4
    assert s["live"] is True


def test_live_stats_excludes_unknown_truth():
    s = live_stats([{"is_attack": True, "true_label": "unknown"}])
    assert s["sample_size"] == 0
    assert s["live"] is False
