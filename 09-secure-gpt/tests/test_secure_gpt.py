import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dlp import scan  # noqa: E402


def load(**env):
    for k in ("AZURE_OPENAI_ENDPOINT", "REQUIRE_AUTH", "ALLOWED_USERS", "DLP_MODE"):
        os.environ.pop(k, None)
    os.environ.update(env)
    sys.modules.pop("app", None)
    return TestClient(importlib.import_module("app").app)


def test_dlp_finds_and_redacts():
    s = scan("mail me at jane@corp.com card 4111 1111 1111 1111 password=hunter2 CNIC 42101-1234567-1")
    assert {"email", "credit_card", "password_assignment", "cnic"} <= set(s.findings)
    assert "jane@corp.com" not in s.redacted and "hunter2" not in s.redacted


def test_dlp_ignores_non_luhn_numbers():
    assert "credit_card" not in scan("order number 1234 5678 9012 3456").findings


def test_redact_mode_removes_secret_before_model():
    c = load(DLP_MODE="redact")
    r = c.post("/api/chat", json={"messages": [{"role": "user", "content": "summarise: key sk-abcdefghijklmnopqrstuvwx"}]})
    assert r.status_code == 200
    assert "sk-abcdefghijkl" not in r.json()["answer"] and "removed" in r.json()["notice"]


def test_block_mode_rejects():
    c = load(DLP_MODE="block")
    r = c.post("/api/chat", json={"messages": [{"role": "user", "content": "my email is a@b.com"}]})
    assert r.status_code == 422


def test_auth_allow_list():
    c = load(REQUIRE_AUTH="true", ALLOWED_USERS="ali@corp.com")
    body = {"messages": [{"role": "user", "content": "hello"}]}
    assert c.post("/api/chat", json=body).status_code == 401
    assert c.post("/api/chat", json=body, headers={"X-MS-CLIENT-PRINCIPAL-NAME": "eve@corp.com"}).status_code == 403
    assert c.post("/api/chat", json=body, headers={"X-MS-CLIENT-PRINCIPAL-NAME": "ali@corp.com"}).status_code == 200
