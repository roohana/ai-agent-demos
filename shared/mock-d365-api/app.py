"""Mock D365 CRM + Finance & Operations REST API for the demos.

Run:  uvicorn app:app --port 8000
Docs: http://localhost:8000/docs

It mimics the *shape* of typical CRM/ERP operations (accounts, opportunities, invoices, sales orders,
purchase requisitions, batch jobs). It is NOT the real D365 OData API; to use real D365, point the
clients at your own sandbox and map the same operations to Dataverse Web API / F&O OData.
"""
from __future__ import annotations

import itertools
import os
from datetime import date
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from data import APPROVAL_LIMITS, fresh_state

API_KEY = os.getenv("MOCK_API_KEY", "demo-key")
STATE = fresh_state()
_ids = itertools.count(1)

app = FastAPI(title="Mock D365 CRM & ERP API", version="1.0.0",
              description="Fictional data. Used by the MCP server, custom connector and Logic App demos.")


def auth(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")


# ---------- models ----------
class OpportunityCreate(BaseModel):
    accountId: str
    name: str = Field(min_length=3, max_length=100)
    amount: float = Field(gt=0)
    closeDate: date
    stage: Literal["Qualify", "Develop", "Propose", "Close"] = "Qualify"


class OpportunityUpdate(BaseModel):
    stage: Optional[Literal["Qualify", "Develop", "Propose", "Close"]] = None
    amount: Optional[float] = Field(default=None, gt=0)
    closeDate: Optional[date] = None


class OrderLine(BaseModel):
    itemId: str
    quantity: int = Field(gt=0, le=10000)


class SalesOrderCreate(BaseModel):
    accountId: str
    lines: list[OrderLine] = Field(min_length=1)


class RequisitionCreate(BaseModel):
    requesterEmail: str
    vendorId: str
    description: str = Field(min_length=3, max_length=200)
    amount: float = Field(gt=0)
    costCenter: str = "CC-100"


class ApprovalDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]
    approver: str
    comment: Optional[str] = None


def _find(rows: list[dict], key: str, value: str, label: str) -> dict:
    for r in rows:
        if r[key] == value:
            return r
    raise HTTPException(status_code=404, detail=f"{label} '{value}' not found")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- CRM ----------
@app.get("/crm/accounts", dependencies=[Depends(auth)])
def search_accounts(search: str = Query(default="", description="Name contains")):
    s = search.lower()
    return [a for a in STATE["accounts"] if s in a["name"].lower()]


@app.get("/crm/accounts/{account_id}", dependencies=[Depends(auth)])
def get_account(account_id: str):
    return _find(STATE["accounts"], "accountId", account_id, "Account")


@app.get("/crm/opportunities", dependencies=[Depends(auth)])
def list_opportunities(accountId: Optional[str] = None):
    return [o for o in STATE["opportunities"] if accountId in (None, o["accountId"])]


@app.post("/crm/opportunities", status_code=201, dependencies=[Depends(auth)])
def create_opportunity(body: OpportunityCreate):
    _find(STATE["accounts"], "accountId", body.accountId, "Account")
    opp = {"opportunityId": f"OPP-{2100 + next(_ids)}", **body.model_dump(mode="json")}
    STATE["opportunities"].append(opp)
    return opp


@app.patch("/crm/opportunities/{opportunity_id}", dependencies=[Depends(auth)])
def update_opportunity(opportunity_id: str, body: OpportunityUpdate):
    opp = _find(STATE["opportunities"], "opportunityId", opportunity_id, "Opportunity")
    opp.update(body.model_dump(mode="json", exclude_none=True))
    return opp


# ---------- ERP ----------
@app.get("/erp/items", dependencies=[Depends(auth)])
def list_items():
    return STATE["items"]


@app.get("/erp/vendors", dependencies=[Depends(auth)])
def list_vendors(search: str = ""):
    return [v for v in STATE["vendors"] if search.lower() in v["name"].lower()]


@app.get("/erp/vendors/{vendor_id}", dependencies=[Depends(auth)])
def get_vendor(vendor_id: str):
    return _find(STATE["vendors"], "vendorId", vendor_id, "Vendor")


@app.get("/erp/invoices", dependencies=[Depends(auth)])
def list_invoices(accountId: Optional[str] = None, status: Optional[Literal["Open", "Paid"]] = None):
    return [i for i in STATE["invoices"]
            if accountId in (None, i["accountId"]) and status in (None, i["status"])]


@app.get("/erp/sales-orders", dependencies=[Depends(auth)])
def list_sales_orders(accountId: Optional[str] = None):
    return [o for o in STATE["sales_orders"] if accountId in (None, o["accountId"])]


@app.post("/erp/sales-orders", status_code=201, dependencies=[Depends(auth)])
def create_sales_order(body: SalesOrderCreate):
    account = _find(STATE["accounts"], "accountId", body.accountId, "Account")
    lines, total = [], 0.0
    for ln in body.lines:
        item = _find(STATE["items"], "itemId", ln.itemId, "Item")
        if ln.quantity > item["onHand"]:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {item['itemId']}: {item['onHand']} on hand")
        lines.append({"itemId": item["itemId"], "quantity": ln.quantity, "unitPrice": item["unitPrice"]})
        total += ln.quantity * item["unitPrice"]
    open_balance = sum(i["amount"] for i in STATE["invoices"] if i["accountId"] == account["accountId"] and i["status"] == "Open")
    if open_balance + total > account["creditLimit"]:
        raise HTTPException(status_code=409, detail=f"Credit limit exceeded: open {open_balance:.2f} + order {total:.2f} > limit {account['creditLimit']}")
    for ln in lines:  # reserve stock only after every check passed
        _find(STATE["items"], "itemId", ln["itemId"], "Item")["onHand"] -= ln["quantity"]
    order = {"salesOrderId": f"SO-{5100 + next(_ids)}", "accountId": account["accountId"], "status": "Created", "total": round(total, 2), "lines": lines}
    STATE["sales_orders"].append(order)
    return order


@app.get("/erp/purchase-orders", dependencies=[Depends(auth)])
def list_purchase_orders(vendorId: Optional[str] = None):
    return [p for p in STATE["purchase_orders"] if vendorId in (None, p["vendorId"])]


@app.post("/erp/purchase-requisitions", status_code=201, dependencies=[Depends(auth)])
def create_requisition(body: RequisitionCreate):
    vendor = _find(STATE["vendors"], "vendorId", body.vendorId, "Vendor")
    if vendor["blocked"]:
        raise HTTPException(status_code=409, detail=f"Vendor {vendor['vendorId']} is blocked for purchasing")
    if body.amount <= APPROVAL_LIMITS["auto"]:
        route = "AutoApproved"
    elif body.amount <= APPROVAL_LIMITS["manager"]:
        route = "ManagerApproval"
    else:
        route = "FinanceApproval"
    req = {"requisitionId": f"PR-{8100 + next(_ids)}", **body.model_dump(), "status": "Approved" if route == "AutoApproved" else "PendingApproval", "approvalRoute": route}
    STATE["purchase_requisitions"].append(req)
    return req


@app.get("/erp/purchase-requisitions/{requisition_id}", dependencies=[Depends(auth)])
def get_requisition(requisition_id: str):
    return _find(STATE["purchase_requisitions"], "requisitionId", requisition_id, "Requisition")


@app.post("/erp/purchase-requisitions/{requisition_id}/decision", dependencies=[Depends(auth)])
def decide_requisition(requisition_id: str, body: ApprovalDecision):
    req = _find(STATE["purchase_requisitions"], "requisitionId", requisition_id, "Requisition")
    if req["status"] != "PendingApproval":
        raise HTTPException(status_code=409, detail=f"Requisition is {req['status']}, not pending")
    req["status"] = body.decision
    req["decidedBy"] = body.approver
    req["decisionComment"] = body.comment
    return req


@app.get("/erp/batch-jobs", dependencies=[Depends(auth)])
def list_batch_jobs(status: Optional[str] = None):
    return [j for j in STATE["batch_jobs"] if status in (None, j["status"])]


@app.get("/erp/batch-jobs/{job_id}", dependencies=[Depends(auth)])
def get_batch_job(job_id: str):
    return _find(STATE["batch_jobs"], "jobId", job_id, "Batch job")


@app.post("/erp/batch-jobs/{job_id}/rerun", dependencies=[Depends(auth)])
def rerun_batch_job(job_id: str):
    job = _find(STATE["batch_jobs"], "jobId", job_id, "Batch job")
    job["status"] = "Waiting"
    job["errorMessage"] = None
    return job
