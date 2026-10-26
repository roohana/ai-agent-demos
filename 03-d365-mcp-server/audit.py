"""Append-only JSON-lines audit log for every tool call."""
from __future__ import annotations

import json
import os
import time
from typing import Any

_SENSITIVE = ("key", "secret", "token", "password")


def _mask(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("***" if any(s in k.lower() for s in _SENSITIVE) else _mask(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask(v) for v in obj]
    return obj


def audit(tool: str, scope: str, arguments: dict, outcome: str, detail: str = "") -> None:
    path = os.getenv("AUDIT_LOG_PATH", "./audit.log")
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool, "scope": scope,
             "arguments": _mask(arguments), "outcome": outcome, "detail": detail[:300]}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
