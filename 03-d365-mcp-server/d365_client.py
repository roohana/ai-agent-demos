"""Thin async HTTP client for the CRM/ERP API (mock by default, real D365 via the same operations)."""
from __future__ import annotations

import os
from typing import Any

import httpx


class D365Error(Exception):
    """Raised with a human-readable message that is safe to show to the agent."""


class D365Client:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = (base_url or os.getenv("D365_API_BASE", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("D365_API_KEY", "demo-key")
        self._transport = transport

    async def request(self, method: str, path: str, *, params: dict | None = None, json: Any = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        async with httpx.AsyncClient(base_url=self.base_url, headers={"x-api-key": self.api_key}, timeout=20, transport=self._transport) as c:
            try:
                r = await c.request(method, path, params=clean, json=json)
            except httpx.HTTPError as e:  # network problems
                raise D365Error(f"Could not reach the CRM/ERP service: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            if isinstance(detail, list):  # FastAPI validation errors
                detail = "; ".join(f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail)
            raise D365Error(f"{r.status_code}: {detail}")
        return r.json()
