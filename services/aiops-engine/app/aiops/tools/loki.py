"""
Loki query tool for the Evidence Agent.
Queries the Loki HTTP API via the internal cluster service URL.
"""

import os
import time
from typing import Optional
import httpx

from ..redact import redact

LOKI_URL = os.getenv("LOKI_URL", "")


async def query_loki_logs(
    namespace: str,
    pod_name: str,
    since_minutes: int = 15,
    limit: int = 80,
    level_filter: Optional[str] = None,
) -> dict:
    """
    Fetch the last N log lines for a pod from Loki.
    Returns raw lines and extracted error/warning lines separately.
    """
    if not LOKI_URL:
        return _mock_logs(pod_name)

    selector = f'{{namespace="{namespace}", pod=~"{pod_name}.*"}}'
    if level_filter:
        selector += f' |= "{level_filter}"'

    end_ns   = int(time.time() * 1e9)
    start_ns = end_ns - (since_minutes * 60 * int(1e9))

    params = {
        "query":     selector,
        "start":     str(start_ns),
        "end":       str(end_ns),
        "limit":     limit,
        "direction": "backward",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return {"error": str(e), "lines": [], "error_lines": []}

    lines = []
    for stream in data.get("data", {}).get("result", []):
        for ts, line in stream.get("values", []):
            lines.append({"timestamp": ts, "line": line})

    lines = sorted(lines, key=lambda x: x["timestamp"])
    # Redact secrets BEFORE the logs leave the cluster to the third-party LLM.
    raw = [redact(l["line"]) for l in lines]

    error_keywords = ("error", "exception", "fatal", "critical", "oom", "killed",
                      "failed", "panic", "traceback", "refused", "timeout")
    error_lines = [l for l in raw if any(k in l.lower() for k in error_keywords)]

    return {
        "pod":         pod_name,
        "namespace":   namespace,
        "line_count":  len(raw),
        "lines":       raw[-50:],         # last 50 lines
        "error_lines": error_lines[-20:], # last 20 error lines
        "last_line":   raw[-1] if raw else "",
    }


def _mock_logs(pod_name: str) -> dict:
    lines = [
        "2026-06-25 09:12:31 INFO  netguard.inference starting (uvicorn on :8000)",
        "2026-06-25 09:12:33 INFO  loading model artifacts from /models",
        "2026-06-25 09:12:39 INFO  LightGBM model loaded — 5 classes, 41 features",
        "2026-06-25 09:13:50 INFO  scored 12000 flows | p95 latency 6.2ms",
        "2026-06-25 09:14:18 WARNING memory usage 503MiB approaching limit 512MiB",
        "2026-06-25 09:14:19 ERROR  worker process killed (SIGKILL) — out of memory",
    ]
    return {
        "pod":         pod_name,
        "namespace":   "netguard",
        "line_count":  len(lines),
        "lines":       lines,
        "error_lines": [lines[-1]],
        "last_line":   lines[-1],
    }
