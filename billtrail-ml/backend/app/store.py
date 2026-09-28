"""SQLite storage for bills and the hash-chained audit log. Swap for Postgres later; keep these function names."""
import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .schemas import StandardBill

DATA = Path(os.getenv("BILLTRAIL_DATA_DIR", "data"))
UPLOADS = DATA / "uploads"
DB = DATA / "billtrail.db"
GENESIS = "GENESIS"
_lock = threading.Lock()


@contextmanager
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    UPLOADS.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS bills(
          id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, file_name TEXT, content_type TEXT, file_path TEXT,
          uploaded_at TEXT, status TEXT, bill_json TEXT, checks_json TEXT, reviewed_by TEXT, error TEXT,
          gstin TEXT, invoice_number TEXT, invoice_date TEXT);
        CREATE TABLE IF NOT EXISTS audit(
          seq INTEGER PRIMARY KEY, action TEXT, bill_id TEXT, actor TEXT, at TEXT, prev_hash TEXT, hash TEXT);
        """)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert(bill_id, sha, name, ctype, path):
    with conn() as c:
        c.execute("INSERT INTO bills(id, sha256, file_name, content_type, file_path, uploaded_at, status) VALUES (?,?,?,?,?,?,'processing')",
                  (bill_id, sha, name, ctype, path, now()))


def by_sha(sha):
    with conn() as c:
        return c.execute("SELECT id FROM bills WHERE sha256=?", (sha,)).fetchone()


def get(bill_id):
    with conn() as c:
        return c.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()


def list_all():
    with conn() as c:
        return c.execute("SELECT * FROM bills ORDER BY uploaded_at DESC").fetchall()


def save_result(bill_id, status, bill: StandardBill, checks: list[dict], reviewed_by=None):
    with conn() as c:
        c.execute("""UPDATE bills SET status=?, bill_json=?, checks_json=?, reviewed_by=COALESCE(?, reviewed_by), error=NULL,
                     gstin=?, invoice_number=?, invoice_date=? WHERE id=?""",
                  (status, bill.model_dump_json(), json.dumps(checks), reviewed_by,
                   (bill.seller.gstin or "").replace(" ", "").upper() or None, bill.invoice.number, bill.invoice.date, bill_id))


def save_failure(bill_id, message):
    with conn() as c:
        c.execute("UPDATE bills SET status='failed', error=? WHERE id=?", (message, bill_id))


def find_duplicate(gstin, number, exclude=None):
    if not gstin or not number:
        return None
    with conn() as c:
        r = c.execute("SELECT id, invoice_date FROM bills WHERE gstin=? AND invoice_number=? AND id<>?",
                      (gstin, number, exclude or "")).fetchone()
    return dict(r) if r else None


def to_api(r) -> dict:
    return {
        "id": r["id"], "status": r["status"], "file_name": r["file_name"], "content_type": r["content_type"],
        "sha256": r["sha256"], "uploaded_at": r["uploaded_at"], "reviewed_by": r["reviewed_by"], "error": r["error"],
        "bill": json.loads(r["bill_json"]) if r["bill_json"] else StandardBill().model_dump(),
        "checks": json.loads(r["checks_json"] or "[]"),
    }


# ---- audit chain: hash = sha256(prev|seq|action|bill_id|actor|at). Same recipe as the frontend's lib/audit.ts ----
def _hash(prev, seq, action, bill_id, actor, at) -> str:
    return hashlib.sha256("|".join(map(str, [prev, seq, action, bill_id, actor, at])).encode()).hexdigest()


def audit_add(action, bill_id, actor):
    with _lock, conn() as c:
        last = c.execute("SELECT seq, hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        seq = last["seq"] + 1 if last else 1
        prev = last["hash"] if last else GENESIS
        at = now()
        c.execute("INSERT INTO audit VALUES (?,?,?,?,?,?,?)",
                  (seq, action, bill_id, actor, at, prev, _hash(prev, seq, action, bill_id, actor, at)))


def audit_all() -> list[dict]:
    """camelCase keys on purpose: the frontend's AuditEntry type uses them."""
    with conn() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY seq").fetchall()
    return [{"seq": r["seq"], "action": r["action"], "billId": r["bill_id"], "actor": r["actor"],
             "at": r["at"], "prevHash": r["prev_hash"], "hash": r["hash"]} for r in rows]


def audit_verify() -> dict:
    prev = GENESIS
    for e in audit_all():
        if e["prevHash"] != prev or _hash(e["prevHash"], e["seq"], e["action"], e["billId"], e["actor"], e["at"]) != e["hash"]:
            return {"ok": False, "brokenAt": e["seq"]}
        prev = e["hash"]
    return {"ok": True}
