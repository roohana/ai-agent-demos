"""D365 MCP server: governed read / write / ops tools for AI agents.

Design rules
  * Every tool declares a scope (read | write | ops). The server only exposes tools whose scope is granted
    through MCP_SCOPES, so one codebase can run as a read-only server for one agent and a read/write server for another.
  * Write tools never write on the first call. They return a preview and a confirmation token; the agent must
    ask the human, then call the same tool again with confirm=true.  (Human-in-the-loop for every change.)
  * Inputs are validated (ids, quantities, amounts) before any call leaves the server.
  * Every call, allowed or refused, is written to the audit log.

Run (stdio):            python server.py
Run (streamable HTTP):  python server.py --http   (for Copilot Studio / remote agents)
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
from datetime import date
from typing import Annotated, Any, Literal

import httpx
from pydantic import Field

from mcp.server.mcpserver import MCPServer

from audit import audit
from d365_client import D365Client, D365Error

SCOPES = {s.strip() for s in os.getenv("MCP_SCOPES", "read").split(",") if s.strip()}
client = D365Client()

mcp = MCPServer(
    name="d365-crm-erp",
    instructions=(
        "Governed tools for Dynamics 365 CRM and ERP data. Read tools are safe. "
        "Write tools return a preview first: show it to the user, get an explicit yes, then call again with the "
        "confirmation_token from the preview and confirm=true."
    ),
)

ACCOUNT_ID = Annotated[str, Field(pattern=r"^ACC-\d{4}$", description="CRM account id, e.g. ACC-1001")]
VENDOR_ID = Annotated[str, Field(pattern=r"^VEN-\d{4}$", description="Vendor id, e.g. VEN-3001")]
ITEM_ID = Annotated[str, Field(pattern=r"^ITM-\d{3}$", description="Item id, e.g. ITM-001")]


def tool(scope: str, **kw):
    """Register a tool only when its scope is granted; wrap it with auditing and error handling."""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **k):
            try:
                result = await fn(*a, **k)
                audit(fn.__name__, scope, k, "ok")
                return result
            except D365Error as e:
                audit(fn.__name__, scope, k, "error", str(e))
                return {"error": str(e)}
        if scope in SCOPES:
            return mcp.tool(**kw)(wrapper)
        return wrapper
    return deco


def _token(tool_name: str, payload: dict) -> str:
    return hashlib.sha256((tool_name + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()[:12]


def _gate(tool_name: str, payload: dict, confirm: bool, token: str | None, summary: str):
    """Return a preview dict unless the caller confirmed with the matching token."""
    expected = _token(tool_name, payload)
    if confirm and token == expected:
        return None
    return {"status": "confirmation_required", "summary": summary, "confirmation_token": expected,
            "next_step": "Show this summary to the user. If they approve, call the same tool again with the same arguments, "
                         "confirm=true and this confirmation_token."}


# ------------------------------------------------------------------ READ
@tool("read", description="Search CRM accounts by name (partial match).")
async def search_customers(name: Annotated[str, Field(min_length=2, max_length=60)]) -> Any:
    return await client.request("GET", "/crm/accounts", params={"search": name})


@tool("read", description="Get one CRM account with its credit limit, plus its open opportunities and open invoice balance.")
async def get_customer_overview(account_id: ACCOUNT_ID) -> Any:
    acct = await client.request("GET", f"/crm/accounts/{account_id}")
    opps = await client.request("GET", "/crm/opportunities", params={"accountId": account_id})
    inv = await client.request("GET", "/erp/invoices", params={"accountId": account_id, "status": "Open"})
    return {"account": acct, "opportunities": opps, "openInvoices": inv,
            "openBalance": round(sum(i["amount"] for i in inv), 2),
            "availableCredit": round(acct["creditLimit"] - sum(i["amount"] for i in inv), 2)}


@tool("read", description="List invoices. Filter by account and status (Open or Paid).")
async def list_invoices(account_id: ACCOUNT_ID | None = None, status: Literal["Open", "Paid"] | None = None) -> Any:
    return await client.request("GET", "/erp/invoices", params={"accountId": account_id, "status": status})


@tool("read", description="List sellable items with price and quantity on hand.")
async def list_items() -> Any:
    return await client.request("GET", "/erp/items")


@tool("read", description="Look up vendors by name, including whether the vendor is blocked for purchasing.")
async def search_vendors(name: Annotated[str, Field(max_length=60)] = "") -> Any:
    return await client.request("GET", "/erp/vendors", params={"search": name})


@tool("read", description="List purchase orders, optionally for one vendor.")
async def list_purchase_orders(vendor_id: VENDOR_ID | None = None) -> Any:
    return await client.request("GET", "/erp/purchase-orders", params={"vendorId": vendor_id})


@tool("read", description="Get the status of a purchase requisition, including its approval route and decision.")
async def get_requisition_status(requisition_id: Annotated[str, Field(pattern=r"^PR-\d+$")]) -> Any:
    return await client.request("GET", f"/erp/purchase-requisitions/{requisition_id}")


@tool("read", description="List batch jobs and their status (Error, Ended, Waiting). Useful for operations questions.")
async def list_batch_jobs(status: Literal["Error", "Ended", "Waiting"] | None = None) -> Any:
    return await client.request("GET", "/erp/batch-jobs", params={"status": status})


# ------------------------------------------------------------------ WRITE (two-step)
@tool("write", description="Create a sales order for an account. Two-step: first call returns a preview + token; call again with confirm=true and the token to create it.")
async def create_sales_order(account_id: ACCOUNT_ID,
                             item_id: ITEM_ID,
                             quantity: Annotated[int, Field(gt=0, le=1000)],
                             confirm: bool = False, confirmation_token: str | None = None) -> Any:
    payload = {"accountId": account_id, "lines": [{"itemId": item_id, "quantity": quantity}]}
    preview = _gate("create_sales_order", payload, confirm, confirmation_token,
                    f"Create a sales order for {account_id}: {quantity} x {item_id}.")
    if preview:
        return preview
    return await client.request("POST", "/erp/sales-orders", json=payload)


@tool("write", description="Create a purchase requisition. Two-step with confirmation. Amount decides the approval route (auto <= 1000, manager <= 10000, otherwise finance).")
async def create_purchase_requisition(requester_email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")],
                                      vendor_id: VENDOR_ID,
                                      description: Annotated[str, Field(min_length=3, max_length=200)],
                                      amount: Annotated[float, Field(gt=0, le=1_000_000)],
                                      confirm: bool = False, confirmation_token: str | None = None) -> Any:
    payload = {"requesterEmail": requester_email, "vendorId": vendor_id, "description": description, "amount": amount}
    preview = _gate("create_purchase_requisition", payload, confirm, confirmation_token,
                    f"Raise a requisition of {amount:,.2f} with {vendor_id} for '{description}' (requester {requester_email}).")
    if preview:
        return preview
    return await client.request("POST", "/erp/purchase-requisitions", json=payload)


@tool("write", description="Create a CRM opportunity for an account. Two-step with confirmation.")
async def create_opportunity(account_id: ACCOUNT_ID,
                             name: Annotated[str, Field(min_length=3, max_length=100)],
                             amount: Annotated[float, Field(gt=0)],
                             close_date: date,
                             confirm: bool = False, confirmation_token: str | None = None) -> Any:
    payload = {"accountId": account_id, "name": name, "amount": amount, "closeDate": close_date.isoformat()}
    preview = _gate("create_opportunity", payload, confirm, confirmation_token,
                    f"Create opportunity '{name}' for {account_id}, amount {amount:,.2f}, closing {close_date}.")
    if preview:
        return preview
    return await client.request("POST", "/crm/opportunities", json=payload)


@tool("write", description="Update the stage, amount or close date of a CRM opportunity. Two-step with confirmation.")
async def update_opportunity(opportunity_id: Annotated[str, Field(pattern=r"^OPP-\d+$")],
                             stage: Literal["Qualify", "Develop", "Propose", "Close"] | None = None,
                             amount: Annotated[float, Field(gt=0)] | None = None,
                             close_date: date | None = None,
                             confirm: bool = False, confirmation_token: str | None = None) -> Any:
    changes = {k: v for k, v in {"stage": stage, "amount": amount, "closeDate": close_date.isoformat() if close_date else None}.items() if v is not None}
    if not changes:
        return {"error": "Nothing to update: provide stage, amount or close_date."}
    payload = {"opportunityId": opportunity_id, **changes}
    preview = _gate("update_opportunity", payload, confirm, confirmation_token, f"Update {opportunity_id}: {changes}.")
    if preview:
        return preview
    return await client.request("PATCH", f"/crm/opportunities/{opportunity_id}", json=changes)


# ------------------------------------------------------------------ OPS
@tool("ops", description="Re-run a failed batch job. Two-step with confirmation.")
async def rerun_batch_job(job_id: Annotated[str, Field(pattern=r"^BATCH-\d+$")],
                          confirm: bool = False, confirmation_token: str | None = None) -> Any:
    payload = {"jobId": job_id}
    preview = _gate("rerun_batch_job", payload, confirm, confirmation_token, f"Re-run batch job {job_id}.")
    if preview:
        return preview
    return await client.request("POST", f"/erp/batch-jobs/{job_id}/rerun")


@tool("ops", description="Start the procure-to-pay approval Logic App for an existing requisition (HTTP trigger). Two-step with confirmation.")
async def trigger_approval_workflow(requisition_id: Annotated[str, Field(pattern=r"^PR-\d+$")],
                                    confirm: bool = False, confirmation_token: str | None = None) -> Any:
    url = os.getenv("LOGIC_APP_URL", "")
    if not url:
        return {"error": "LOGIC_APP_URL is not configured on this server."}
    payload = {"requisitionId": requisition_id}
    preview = _gate("trigger_approval_workflow", payload, confirm, confirmation_token, f"Start the approval workflow for {requisition_id}.")
    if preview:
        return preview
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json=payload)
    if r.status_code >= 400:
        raise D365Error(f"Logic App returned {r.status_code}")
    return {"started": True, "requisitionId": requisition_id, "workflowStatus": r.status_code}


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
