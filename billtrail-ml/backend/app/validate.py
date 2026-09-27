"""Rule checks. We never trust the AI blindly: every extracted bill is checked here.

References: [1] CGST Rules 2017, Rule 46; [2] Drugs and Cosmetics Rules 1945, Rule 65;
[3] GSTN GSTIN structure (15 characters, last one is a check digit).
"""
import re
from calendar import monthrange
from datetime import date
from typing import Callable

from .schemas import StandardBill

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
TOLERANCE = 1.0   # rupees; bills round to the nearest rupee or paisa


def gstin_check_digit(first14: str) -> str:
    """Mod-36 check digit used by GSTN (alternate weights 1 and 2)."""
    total = 0
    for i, ch in enumerate(first14):
        product = CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return CHARS[(36 - total % 36) % 36]


def valid_state_code(code: str) -> bool:
    n = int(code)
    return 1 <= n <= 38 or n == 97


def gstin_problem(gstin: str | None) -> str | None:
    """Return None if the GSTIN is valid, else a plain-language reason."""
    if not gstin:
        return "No GSTIN found."
    g = re.sub(r"\s", "", gstin.upper())
    if not GSTIN_RE.match(g):
        return f'"{g}" does not follow the 15-character GSTIN pattern.'
    if not valid_state_code(g[:2]):
        return f"State code {g[:2]} does not exist."
    expected = gstin_check_digit(g[:14])
    if expected != g[14]:
        return f"The last character (check digit) should be {expected}, not {g[14]}. The number was misread, mistyped or is fake."
    return None


def normalise_gstin(g: str | None) -> str | None:
    return re.sub(r"\s", "", g.upper()) if g else None


def parse_date(s: str | None) -> date | None:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s or "")
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def parse_expiry(s: str | None) -> date | None:
    """YYYY-MM -> last day of that month (medicines are usable until month end)."""
    m = re.match(r"^(\d{4})-(\d{2})", s or "")
    if not m:
        return None
    y, mo = int(m[1]), int(m[2])
    if not 1 <= mo <= 12:
        return None
    return date(y, mo, monthrange(y, mo)[1])


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


def _f(v) -> str:
    return "–" if v is None else f"{v:,.2f}"


DuplicateLookup = Callable[[str | None, str | None], dict | None]


def run_checks(bill: StandardBill, find_duplicate: DuplicateLookup | None = None, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out: list[dict] = []

    def add(code, label, status, detail, ref=""):
        out.append({"code": code, "label": label, "status": status, "detail": detail, "ref": ref})

    s, inv, t, tax = bill.seller, bill.invoice, bill.totals, bill.tax
    items = [i for i in bill.items if any(v not in (None, "") for v in i.model_dump().values())]

    # 1. Mandatory tax-invoice fields [1]
    missing = [label for label, val in [("seller name", s.name), ("address", s.address), ("GSTIN", s.gstin),
                                        ("invoice number", inv.number), ("invoice date", inv.date)] if not val]
    if not items:
        missing.append("item lines")
    add("required_fields", "Bill shows what a GST tax invoice must show", "fail" if missing else "pass",
        f"Missing: {', '.join(missing)}." if missing else "Seller name, address, GSTIN, invoice number, date and items are present.", "[1]")

    # 2. GSTIN pattern, state code and check digit [3]
    problem = gstin_problem(s.gstin)
    g = normalise_gstin(s.gstin)
    add("gstin_valid", "GSTIN is a real, correctly formed number", "fail" if problem else "pass",
        problem or f"Pattern, state code ({g[:2]}) and check digit are all correct.", "[3]")

    pharmacy = (bill.bill_type or "pharmacy") == "pharmacy"
    # 3-4. Pharmacy record-keeping fields [2]
    if pharmacy:
        add("drug_licence", "Pharmacy drug licence number is shown", "pass" if s.drug_licence_no else "warn",
            f"Licence: {s.drug_licence_no}" if s.drug_licence_no else "Not found. Some insurers ask for it.", "[2]")
        no_batch = [i.name or "a line" for i in items if not i.batch or not i.expiry]
        add("batch_expiry", "Every medicine has a batch number and expiry", "warn" if no_batch else "pass",
            f"{', '.join(no_batch)} missing batch or expiry." if no_batch else f"All {len(items)} lines have both.", "[2]")

    # 5. Dates
    d0 = parse_date(inv.date)
    if inv.date and not d0:
        add("date_format", "Bill date is a real date", "fail", f'"{inv.date}" is not a valid date (expected YYYY-MM-DD).')
    if d0:
        if pharmacy:
            expired = [f"{i.name or 'item'} (expiry {i.expiry})" for i in items
                       if (e := parse_expiry(i.expiry)) and e < d0]
            add("not_expired", "No medicine was already expired when sold", "fail" if expired else "pass",
                f"{', '.join(expired)} expired before the bill date." if expired else "All expiry dates are after the bill date.", "[2]")
        if d0 > today:
            add("future_date", "Bill date is not in the future", "fail", f"Bill date {inv.date} is after today.")

    # 6. Arithmetic
    line_sum = sum(i.amount or 0 for i in items)
    if items and t.subtotal is not None:
        add("lines_sum", "Line amounts add up to the sub-total", "pass" if _near(line_sum, t.subtotal) else "fail",
            f"Lines add up to ₹{_f(line_sum)}; bill says ₹{_f(t.subtotal)}.")
    disc = t.discount or 0
    total_tax = t.total_tax if t.total_tax is not None else sum(x or 0 for x in (tax.cgst, tax.sgst, tax.igst))
    if t.grand_total is not None and t.subtotal is not None:
        inclusive = _near(t.subtotal - disc, t.grand_total)       # MRP already includes GST (common in pharmacies)
        exclusive = _near(t.subtotal - disc + total_tax, t.grand_total)
        ok = inclusive or exclusive
        add("grand_total", "Grand total matches sub-total, discount and tax", "pass" if ok else "fail",
            f"Checks out ({'prices include GST' if inclusive else 'GST added on top'})." if ok else
            f"Expected ₹{_f(t.subtotal - disc)} (GST included) or ₹{_f(t.subtotal - disc + total_tax)} (GST added), but bill says ₹{_f(t.grand_total)}.")
    else:
        add("grand_total", "Grand total matches sub-total, discount and tax", "warn",
            "Sub-total or grand total is missing, so the math could not be checked.")
    if t.taxable_value is not None and t.grand_total is not None and total_tax:
        add("taxable_plus_tax", "Taxable value plus GST equals the total",
            "pass" if _near(t.taxable_value + total_tax, t.grand_total) else "warn",
            f"₹{_f(t.taxable_value)} + ₹{_f(total_tax)} = ₹{_f(t.taxable_value + total_tax)}; total is ₹{_f(t.grand_total)}.", "[1]")
    if tax.cgst is not None or tax.sgst is not None:
        equal = tax.cgst is not None and tax.sgst is not None and abs(tax.cgst - tax.sgst) <= 0.05
        add("cgst_sgst", "CGST equals SGST (sale within one state)", "pass" if equal else "warn",
            f"CGST ₹{_f(tax.cgst)}, SGST ₹{_f(tax.sgst)}.", "[1]")

    # 7. Duplicates (same GSTIN + invoice number). Same-file duplicates are blocked at upload by SHA-256.
    if find_duplicate:
        dup = find_duplicate(g, inv.number)
        add("not_duplicate", "This bill was not uploaded before", "fail" if dup else "pass",
            f"Same GSTIN and invoice number as bill {dup['id']} ({dup.get('invoice_date') or 'no date'})." if dup else "No matching bill in the records.")
    return out


def status_of(checks: list[dict], confidence: float | None, threshold: float = 0.7) -> str:
    if any(c["status"] == "fail" for c in checks):
        return "review"
    if confidence is not None and confidence < threshold:
        return "review"
    return "verified"
