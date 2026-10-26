"""Run the same procure-to-pay logic as workflow.json locally, against the mock API.

Usage:
  (terminal 1)  cd ../shared/mock-d365-api && uvicorn app:app --port 8000
  (terminal 2)  python simulate_workflow.py --amount 2500 --decision Approved

It creates a requisition, follows the approval route, records the decision and prints each step the way the
Logic App run history would. The approval email step is simulated by the --decision flag.
"""
import argparse
import os

import httpx

BASE = os.getenv("D365_API_BASE", "http://localhost:8000")
H = {"x-api-key": os.getenv("D365_API_KEY", "demo-key")}


def step(name, detail=""):
    print(f"[Succeeded] {name} {detail}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--amount", type=float, default=2500)
    p.add_argument("--vendor", default="VEN-3001")
    p.add_argument("--decision", choices=["Approved", "Rejected"], default="Approved")
    a = p.parse_args()
    with httpx.Client(base_url=BASE, headers=H, timeout=20) as c:
        r = c.post("/erp/purchase-requisitions", json={"requesterEmail": "employee@example.com", "vendorId": a.vendor,
                                                      "description": "Demo purchase", "amount": a.amount})
        if r.status_code >= 400:
            print(f"[Failed] Create requisition -> {r.status_code} {r.json()['detail']}")
            return
        req = r.json()
        step("Create requisition (HTTP trigger input)", req["requisitionId"])
        req = c.get(f"/erp/purchase-requisitions/{req['requisitionId']}").json()
        step("Get_requisition", f"status={req['status']} route={req['approvalRoute']}")
        if req["status"] == "PendingApproval":
            approver = "finance.approvers@example.com" if req["approvalRoute"] == "FinanceApproval" else "line.manager@example.com"
            step("Send_approval_email (simulated)", f"to {approver}, selected option -> {a.decision}")
            req = c.post(f"/erp/purchase-requisitions/{req['requisitionId']}/decision",
                         json={"decision": a.decision, "approver": approver, "comment": "simulated run"}).json()
            step("Write_decision_to_ERP", f"status={req['status']}")
        else:
            step("Needs_approval", "skipped (auto-approved under threshold)")
        step("Notify_requester", f"-> {req['requesterEmail']}")
        print("Respond_success: 200", {"requisitionId": req["requisitionId"], "result": "processed"})


if __name__ == "__main__":
    main()
