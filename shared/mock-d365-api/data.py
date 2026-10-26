"""In-memory sample data that imitates a small D365 CRM (Sales) + Finance & Operations tenant.

All names, amounts and IDs are fictional. Nothing here comes from a client system.
"""
from copy import deepcopy

ACCOUNTS = [
    {"accountId": "ACC-1001", "name": "Northwind Traders", "city": "Karachi", "ownerName": "Sara Khan", "creditLimit": 50000, "currency": "USD"},
    {"accountId": "ACC-1002", "name": "Contoso Retail", "city": "Lahore", "ownerName": "Ali Raza", "creditLimit": 80000, "currency": "USD"},
    {"accountId": "ACC-1003", "name": "Fabrikam Logistics", "city": "Dubai", "ownerName": "Sara Khan", "creditLimit": 120000, "currency": "USD"},
    {"accountId": "ACC-1004", "name": "Adventure Works Health", "city": "London", "ownerName": "Omar Sheikh", "creditLimit": 30000, "currency": "GBP"},
]

OPPORTUNITIES = [
    {"opportunityId": "OPP-2001", "accountId": "ACC-1001", "name": "Q4 Warehouse Upgrade", "stage": "Propose", "amount": 42000, "closeDate": "2026-12-15"},
    {"opportunityId": "OPP-2002", "accountId": "ACC-1002", "name": "POS Hardware Refresh", "stage": "Qualify", "amount": 18500, "closeDate": "2027-01-20"},
    {"opportunityId": "OPP-2003", "accountId": "ACC-1003", "name": "Fleet Tracking Rollout", "stage": "Develop", "amount": 96000, "closeDate": "2027-02-28"},
]

ITEMS = [
    {"itemId": "ITM-001", "name": "Barcode Scanner", "unitPrice": 120.0, "onHand": 340},
    {"itemId": "ITM-002", "name": "Thermal Printer", "unitPrice": 310.0, "onHand": 85},
    {"itemId": "ITM-003", "name": "Handheld Terminal", "unitPrice": 540.0, "onHand": 40},
    {"itemId": "ITM-004", "name": "Shelf Label Kit", "unitPrice": 25.0, "onHand": 1200},
]

VENDORS = [
    {"vendorId": "VEN-3001", "name": "Globex Supplies", "paymentTerms": "Net30", "blocked": False},
    {"vendorId": "VEN-3002", "name": "Initech Components", "paymentTerms": "Net45", "blocked": False},
    {"vendorId": "VEN-3003", "name": "Umbrella Parts", "paymentTerms": "Net15", "blocked": True},
]

INVOICES = [
    {"invoiceId": "INV-4001", "accountId": "ACC-1001", "amount": 12400.0, "dueDate": "2026-10-10", "status": "Open"},
    {"invoiceId": "INV-4002", "accountId": "ACC-1001", "amount": 5800.0, "dueDate": "2026-11-05", "status": "Open"},
    {"invoiceId": "INV-4003", "accountId": "ACC-1002", "amount": 22000.0, "dueDate": "2026-09-01", "status": "Paid"},
    {"invoiceId": "INV-4004", "accountId": "ACC-1003", "amount": 40300.0, "dueDate": "2026-10-30", "status": "Open"},
]

SALES_ORDERS = [
    {"salesOrderId": "SO-5001", "accountId": "ACC-1002", "status": "Confirmed", "total": 3100.0,
     "lines": [{"itemId": "ITM-002", "quantity": 10, "unitPrice": 310.0}]},
]

PURCHASE_ORDERS = [
    {"purchaseOrderId": "PO-6001", "vendorId": "VEN-3001", "status": "Received", "total": 8400.0},
    {"purchaseOrderId": "PO-6002", "vendorId": "VEN-3002", "status": "Open", "total": 15250.0},
]

PURCHASE_REQUISITIONS = []

BATCH_JOBS = [
    {"jobId": "BATCH-7001", "name": "Inventory closing", "status": "Error", "lastRun": "2026-10-25T23:10:00Z",
     "durationMinutes": 94, "errorMessage": "SQL timeout while updating InventTrans (lock wait 30s exceeded)"},
    {"jobId": "BATCH-7002", "name": "Sales invoice posting", "status": "Ended", "lastRun": "2026-10-25T22:00:00Z",
     "durationMinutes": 12, "errorMessage": None},
    {"jobId": "BATCH-7003", "name": "Vendor payment proposal", "status": "Waiting", "lastRun": "2026-10-24T22:00:00Z",
     "durationMinutes": 7, "errorMessage": None},
]

# Approval limits (USD) used by the procure-to-pay demo
APPROVAL_LIMITS = {"auto": 1000.0, "manager": 10000.0}


def fresh_state() -> dict:
    return deepcopy({
        "accounts": ACCOUNTS, "opportunities": OPPORTUNITIES, "items": ITEMS, "vendors": VENDORS,
        "invoices": INVOICES, "sales_orders": SALES_ORDERS, "purchase_orders": PURCHASE_ORDERS,
        "purchase_requisitions": PURCHASE_REQUISITIONS, "batch_jobs": BATCH_JOBS,
    })
