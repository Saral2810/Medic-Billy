from datetime import date

from app.schemas import StandardBill
from app.validate import gstin_check_digit, gstin_problem, run_checks, status_of

VALID = "27AAPFU0939F1ZV"   # widely published sample GSTIN with a correct check digit


def base_bill(**over):
    d = {"bill_type": "pharmacy",
         "seller": {"name": "Shri Balaji Medical Store", "address": "Rohini, Delhi", "gstin": VALID, "drug_licence_no": "DL-1"},
         "invoice": {"number": "SBM/0457", "date": "2026-09-18"},
         "patient_name": "Ramesh Kumar",
         "items": [{"name": "Paracetamol 650", "batch": "P1", "expiry": "2028-08", "qty": 2, "amount": 65.0},
                   {"name": "Pantoprazole 40", "batch": "P2", "expiry": "2027-12", "qty": 1, "amount": 145.0}],
         "tax": {"cgst": 11.25, "sgst": 11.25},
         "totals": {"subtotal": 210.0, "discount": 0, "taxable_value": 187.5, "total_tax": 22.5, "grand_total": 210.0},
         "confidence": 0.95}
    d.update(over)
    return StandardBill.model_validate(d)


def by_code(checks):
    return {c["code"]: c["status"] for c in checks}


def test_gstin_check_digit_known_sample():
    assert gstin_check_digit(VALID[:14]) == "V"
    assert gstin_problem(VALID) is None


def test_gstin_wrong_check_digit_fails():
    assert "check digit" in gstin_problem(VALID[:14] + "A")


def test_gstin_bad_pattern_and_state():
    assert "pattern" in gstin_problem("12345")
    assert "State code" in gstin_problem("99" + VALID[2:])


def test_clean_bill_is_verified():
    checks = run_checks(base_bill(), today=date(2026, 9, 26))
    assert all(s != "fail" for s in by_code(checks).values()), checks
    assert status_of(checks, 0.95) == "verified"


def test_money_strings_are_parsed():
    b = base_bill(totals={"subtotal": "₹210.00", "grand_total": "Rs. 210", "discount": ""})
    assert b.totals.subtotal == 210.0 and b.totals.grand_total == 210.0 and b.totals.discount is None


def test_total_mismatch_fails():
    b = base_bill(totals={"subtotal": 210.0, "grand_total": 260.0})
    assert by_code(run_checks(b, today=date(2026, 9, 26)))["grand_total"] == "fail"


def test_gst_added_on_top_passes():
    b = base_bill(totals={"subtotal": 187.5, "total_tax": 22.5, "grand_total": 210.0})
    b.items[0].amount, b.items[1].amount = 60.0, 127.5
    assert by_code(run_checks(b, today=date(2026, 9, 26)))["grand_total"] == "pass"


def test_expired_medicine_fails():
    b = base_bill()
    b.items[0].expiry = "2026-06"
    assert by_code(run_checks(b, today=date(2026, 9, 26)))["not_expired"] == "fail"


def test_missing_batch_is_a_warning_not_failure():
    b = base_bill()
    b.items[1].batch = None
    c = run_checks(b, today=date(2026, 9, 26))
    assert by_code(c)["batch_expiry"] == "warn" and status_of(c, 0.9) == "verified"


def test_duplicate_detected():
    c = run_checks(base_bill(), find_duplicate=lambda g, n: {"id": "x", "invoice_date": "2026-09-18"}, today=date(2026, 9, 26))
    assert by_code(c)["not_duplicate"] == "fail"


def test_low_confidence_needs_review():
    assert status_of(run_checks(base_bill(), today=date(2026, 9, 26)), 0.4) == "review"
