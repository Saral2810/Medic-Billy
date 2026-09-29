"""HTTP API for the BillTrail frontend. Run from billtrail-ml/backend:

    BILLTRAIL_READER=fake uvicorn app.api:app --reload --port 8000     # no model needed (laptop)
    uvicorn app.api:app --reload --port 8000                           # real pipeline (needs ML deps/GPU)

Roles: patient = own bills only; reviewer = all bills; admin = all bills + manages roles.
The first account ever created becomes the admin.
"""
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import auth, store
from .auth import current_user, require_admin
from .schemas import ClaimRequest, Invoice, Item, Seller, StandardBill, Tax, Totals
from .validate import gstin_check_digit, run_checks, status_of

ALLOWED = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_BYTES = 15 * 1024 * 1024
STAFF = ("reviewer", "admin")

app = FastAPI(title="BillTrail API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("BILLTRAIL_CORS", "http://localhost:3000").split(","),
                   allow_methods=["*"], allow_headers=["*"])
store.init()


# ---------- reading a bill ----------
def _fake_bill() -> StandardBill:
    """Stand-in for the model so the frontend can be tested end to end. Has a wrong total on purpose."""
    g = "23ABCDE1234F1Z"
    return StandardBill(
        seller=Seller(name="Shree Balaji Medicals", address="12, Vijay Nagar, Indore, MP", gstin=g + gstin_check_digit(g),
                      drug_licence_no="MP-IND-20B-1123", phone="0731 400 2211"),
        invoice=Invoice(number=f"SBM/{int(time.time()) % 10000}", date=time.strftime("%Y-%m-%d")),
        patient_name="Rohan Verma", doctor_name="Dr. A. Sharma",
        items=[Item(name="Dolo 650 Tab", hsn="30049099", batch="DL2391", expiry="2027-08", qty=2, mrp=32, rate=30, amount=60),
               Item(name="Azithral 500 Tab", hsn="30042019", batch="AZ5521", expiry="2027-03", qty=1, mrp=118.5, rate=110, amount=110),
               Item(name="ORS Sachet", hsn="30049099", expiry="2027-01", qty=3, mrp=22, rate=20, amount=60)],
        tax=Tax(gst_rate=12, cgst=13.8, sgst=13.8),
        totals=Totals(subtotal=230, discount=0, taxable_value=230, total_tax=27.6, grand_total=275.6),
        confidence=0.82, unreadable=["items.2.batch", "totals.grand_total"])


def _read(data: bytes, content_type: str) -> StandardBill:
    if os.getenv("BILLTRAIL_READER", "real") == "fake":
        time.sleep(2)
        return _fake_bill()
    from .pipeline import read_bill  # imported late so the API starts even without ML dependencies
    return read_bill(data, content_type).bill


def _process(bill_id: str):
    row = store.get(bill_id)
    try:
        bill = _read(Path(row["file_path"]).read_bytes(), row["content_type"])
        checks = run_checks(bill, lambda g, n: store.find_duplicate(g, n, row["owner_id"], exclude=bill_id))
        store.save_result(bill_id, status_of(checks, bill.confidence), bill, checks)
        store.audit_add("ai_read", bill_id, "worker")
    except Exception as e:  # shown to the user on the Add a bill page
        store.save_failure(bill_id, f"{type(e).__name__}: {e}")


def _row(bill_id: str, user: dict):
    """404 (not 403) for other people's bills, so their existence is not revealed."""
    row = store.get(bill_id)
    if not row or (user["role"] not in STAFF and row["owner_id"] != user["id"]):
        raise HTTPException(404, "Bill not found")
    return row


# ---------- accounts ----------
class Credentials(BaseModel):
    email: str
    password: str


class Registration(Credentials):
    name: str


def _session(user: dict) -> dict:
    return {"token": auth.make_token(user), "user": user}


@app.post("/auth/register")
def register(r: Registration):
    email = r.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Enter a valid email address.")
    if len(r.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    if not r.name.strip():
        raise HTTPException(422, "Enter your name.")
    if store.user_login_row(email):
        raise HTTPException(409, "An account with this email already exists.")
    role = "admin" if store.count_users() == 0 else "patient"
    return _session(store.create_user(email, r.name.strip(), role, auth.hash_password(r.password)))


@app.post("/auth/login")
def login(c: Credentials):
    row = store.user_login_row(c.email.strip().lower())
    if not row or not auth.verify_password(c.password, row["pw_hash"]):
        raise HTTPException(401, "Wrong email or password.")
    return _session({k: row[k] for k in ("id", "email", "name", "role")})


@app.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return user


class RoleChange(BaseModel):
    role: Literal["patient", "reviewer", "admin"]


@app.get("/users")
def users(_: dict = Depends(require_admin)):
    return store.list_users()


@app.put("/users/{user_id}/role")
def change_role(user_id: str, body: RoleChange, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "You cannot change your own role.")
    if not store.user_by_id(user_id):
        raise HTTPException(404, "User not found")
    store.set_role(user_id, body.role)
    return store.user_by_id(user_id)


# ---------- bills ----------
@app.post("/bills")
async def upload(bg: BackgroundTasks, file: UploadFile = File(...), user: dict = Depends(current_user)):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "Upload a PDF, PNG, JPG or WebP file.")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 15 MB.")
    sha = hashlib.sha256(data).hexdigest()
    if store.by_sha(sha, user["id"]):
        raise HTTPException(409, "You already uploaded this exact file.")
    bill_id = uuid.uuid4().hex[:8]
    path = store.UPLOADS / f"{bill_id}{ALLOWED[file.content_type]}"
    path.write_bytes(data)
    store.insert(bill_id, user["id"], sha, file.filename or path.name, file.content_type, str(path))
    store.audit_add("uploaded", bill_id, user["name"])
    bg.add_task(_process, bill_id)
    return store.to_api(store.get(bill_id))


@app.get("/bills")
def list_bills(user: dict = Depends(current_user)):
    rows = store.list_for(None if user["role"] in STAFF else user["id"])
    return [store.to_api(r) for r in rows]


@app.get("/bills/{bill_id}")
def get_bill(bill_id: str, user: dict = Depends(current_user)):
    return store.to_api(_row(bill_id, user))


@app.get("/bills/{bill_id}/file")
def original(bill_id: str, user: dict = Depends(current_user)):
    row = _row(bill_id, user)
    return FileResponse(row["file_path"], media_type=row["content_type"])


@app.put("/bills/{bill_id}")
def correct(bill_id: str, bill: StandardBill, user: dict = Depends(current_user)):
    row = _row(bill_id, user)
    if bill.totals.taxable_value is None and bill.totals.subtotal is not None:
        bill.totals.taxable_value = round(bill.totals.subtotal - (bill.totals.discount or 0), 2)
    bill.unreadable = []
    checks = run_checks(bill, lambda g, n: store.find_duplicate(g, n, row["owner_id"], exclude=bill_id))
    store.save_result(bill_id, status_of(checks, None), bill, checks, reviewed_by=user["name"])  # a person checked it: ignore model confidence
    store.audit_add("corrected", bill_id, user["name"])
    return store.to_api(store.get(bill_id))


@app.post("/claims")
def claim_bundle(req: ClaimRequest, user: dict = Depends(current_user)):
    entries = []
    for bill_id in req.bill_ids:
        row = _row(bill_id, user)
        b = StandardBill(**json.loads(row["bill_json"]))
        t = b.totals
        entries.append({"resource": {
            "resourceType": "Invoice", "id": bill_id, "status": "issued", "date": b.invoice.date,
            "identifier": [{"system": f"urn:gstin:{b.seller.gstin}", "value": b.invoice.number}],
            "issuer": {"display": b.seller.name}, "subject": {"display": b.patient_name},
            "lineItem": [{"sequence": n + 1, "chargeItemCodeableConcept": {"text": i.name},
                          "priceComponent": [{"type": "base", "amount": {"value": i.amount, "currency": "INR"}}]}
                         for n, i in enumerate(b.items)],
            "totalNet": {"value": (t.subtotal or 0) - (t.discount or 0), "currency": "INR"},
            "totalGross": {"value": t.grand_total, "currency": "INR"}}})
        store.audit_add("exported", bill_id, user["name"])
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


# ---------- paper trail ----------
@app.get("/audit")
def audit(user: dict = Depends(current_user)):
    entries = store.audit_all()
    if user["role"] in STAFF:
        return entries
    mine = {r["id"] for r in store.list_for(user["id"])}
    return [e for e in entries if e["billId"] in mine]


@app.get("/audit/verify")
def audit_verify(_: dict = Depends(current_user)):
    return store.audit_verify()
