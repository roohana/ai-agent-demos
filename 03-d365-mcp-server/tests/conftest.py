"""Starts the shared mock D365 API on a free port for the whole test session."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

API_DIR = Path(__file__).resolve().parents[2] / "shared" / "mock-d365-api"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session", autouse=True)
def mock_api():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", str(port), "--log-level", "warning"],
                            cwd=API_DIR, env={**os.environ, "MOCK_API_KEY": "demo-key"})
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("mock API did not start")
    os.environ["D365_API_BASE"] = base
    os.environ["D365_API_KEY"] = "demo-key"
    yield base
    proc.terminate()
