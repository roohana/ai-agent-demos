"""In-process tests: MCP client <-> MCP server <-> mock API (started separately on :8000)."""
import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def load(scopes: str):
    os.environ["MCP_SCOPES"] = scopes
    os.environ["AUDIT_LOG_PATH"] = "/tmp/test-audit.log"
    if "server" in sys.modules:
        del sys.modules["server"]
    return importlib.import_module("server")


async def call(server, name, args):
    from mcp.client.client import Client
    async with Client(server.mcp) as c:
        res = await c.call_tool(name, args)
        text = res.content[0].text if res.content else ""
        try:
            return json.loads(text)
        except ValueError:
            return text


@pytest.mark.asyncio
async def test_scopes_control_tool_list():
    from mcp.client.client import Client
    ro = load("read")
    async with Client(ro.mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert "search_customers" in names and "create_sales_order" not in names and "rerun_batch_job" not in names
    rw = load("read,write,ops")
    async with Client(rw.mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert {"create_sales_order", "rerun_batch_job"} <= names


@pytest.mark.asyncio
async def test_read_overview():
    s = load("read")
    out = await call(s, "get_customer_overview", {"account_id": "ACC-1001"})
    assert out["account"]["name"] == "Northwind Traders"
    assert out["openBalance"] > 0


@pytest.mark.asyncio
async def test_write_requires_confirmation():
    s = load("read,write")
    preview = await call(s, "create_purchase_requisition",
                         {"requester_email": "a@b.com", "vendor_id": "VEN-3001", "description": "Monitors", "amount": 2500})
    assert preview["status"] == "confirmation_required"
    # wrong token must not write
    bad = await call(s, "create_purchase_requisition",
                     {"requester_email": "a@b.com", "vendor_id": "VEN-3001", "description": "Monitors", "amount": 2500,
                      "confirm": True, "confirmation_token": "nope"})
    assert bad["status"] == "confirmation_required"
    done = await call(s, "create_purchase_requisition",
                      {"requester_email": "a@b.com", "vendor_id": "VEN-3001", "description": "Monitors", "amount": 2500,
                       "confirm": True, "confirmation_token": preview["confirmation_token"]})
    assert done["approvalRoute"] == "ManagerApproval" and done["status"] == "PendingApproval"


@pytest.mark.asyncio
async def test_business_rule_errors_are_returned_not_raised():
    s = load("read,write")
    args = {"requester_email": "a@b.com", "vendor_id": "VEN-3003", "description": "Parts", "amount": 500}
    p = await call(s, "create_purchase_requisition", args)
    out = await call(s, "create_purchase_requisition", {**args, "confirm": True, "confirmation_token": p["confirmation_token"]})
    assert "blocked" in out["error"]


@pytest.mark.asyncio
async def test_input_validation_rejects_bad_ids():
    from mcp.client.client import Client
    s = load("read")
    async with Client(s.mcp) as c:
        res = await c.call_tool("get_customer_overview", {"account_id": "bad-id"})
    assert res.is_error
