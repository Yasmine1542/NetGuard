"""Thin HTTP proxies to other services and to Prometheus/Loki.

Every call degrades gracefully: on failure it returns a structured error or empty
dict rather than raising, so one unavailable backend never 500s the dashboard.
"""

from __future__ import annotations

from typing import Any

import httpx


class Upstreams:
    def __init__(
        self,
        inference_url: str,
        aiops_url: str,
        prometheus_url: str,
        loki_url: str,
        timeout: float = 8.0,
    ) -> None:
        self._inference = httpx.AsyncClient(base_url=inference_url, timeout=5.0)
        self._aiops = httpx.AsyncClient(base_url=aiops_url, timeout=5.0)
        self._http = httpx.AsyncClient(timeout=timeout)
        self.prometheus_url = prometheus_url
        self.loki_url = loki_url

    async def model_info(self) -> dict[str, Any]:
        try:
            r = await self._inference.get("/model-info")
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    async def cluster_summary(self) -> dict[str, Any]:
        try:
            r = await self._aiops.get("/cluster")
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    async def prometheus(self, query: str, start: str, end: str, step: str) -> dict[str, Any]:
        if not self.prometheus_url:
            return {"error": "prometheus not configured", "data": None}
        params: dict[str, Any] = {"query": query}
        if start and end:
            params.update({"start": start, "end": end, "step": step})
            url = f"{self.prometheus_url}/api/v1/query_range"
        else:
            url = f"{self.prometheus_url}/api/v1/query"
        try:
            r = await self._http.get(url, params=params)
            return r.json()
        except Exception as exc:
            return {"error": str(exc), "data": None}

    async def loki(self, query: str, limit: int, since: str) -> dict[str, Any]:
        if not self.loki_url:
            return {"error": "loki not configured", "data": None}
        try:
            r = await self._http.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params={"query": query, "limit": limit, "since": since},
            )
            return r.json()
        except Exception as exc:
            return {"error": str(exc), "data": None}

    async def close(self) -> None:
        await self._inference.aclose()
        await self._aiops.aclose()
        await self._http.aclose()
