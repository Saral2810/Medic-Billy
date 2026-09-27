"""The standard bill format. Every bill, whatever it looks like, is converted into this shape.

Field choices follow CGST Rule 46 (tax invoice contents), Drugs and Cosmetics Rules Rule 65
(pharmacy sale records) and the HL7 FHIR R4 Invoice resource. See README references.
"""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


def _to_num(v):
    """Accept 1234.5, "1,234.50", "₹ 99" or "" from the LLM; return float or None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[₹,\s]|Rs\.?", "", str(v), flags=re.I)
    try:
        return float(s)
    except ValueError:
        return None


def _to_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


Num = Annotated[float | None, BeforeValidator(_to_num)]
Str = Annotated[str | None, BeforeValidator(_to_str)]


class Seller(BaseModel):
    name: Str = None
    address: Str = None
    gstin: Str = None
    drug_licence_no: Str = None
    phone: Str = None


class Invoice(BaseModel):
    number: Str = None
    date: Str = None          # YYYY-MM-DD


class Item(BaseModel):
    name: Str = None
    hsn: Str = None
    batch: Str = None
    expiry: Str = None        # YYYY-MM
    qty: Num = None
    mrp: Num = None
    rate: Num = None
    discount: Num = None
    amount: Num = None


class Tax(BaseModel):
    gst_rate: Num = None
    cgst: Num = None
    sgst: Num = None
    igst: Num = None


class Totals(BaseModel):
    subtotal: Num = None
    discount: Num = None
    taxable_value: Num = None
    total_tax: Num = None
    grand_total: Num = None


class StandardBill(BaseModel):
    bill_type: Literal["pharmacy", "lab", "hospital"] | None = "pharmacy"
    seller: Seller = Field(default_factory=Seller)
    invoice: Invoice = Field(default_factory=Invoice)
    patient_name: Str = None
    doctor_name: Str = None
    items: list[Item] = Field(default_factory=list)
    tax: Tax = Field(default_factory=Tax)
    totals: Totals = Field(default_factory=Totals)
    confidence: Num = None                    # 0..1, the AI's own estimate
    unreadable: list[str] = Field(default_factory=list)


class ClaimRequest(BaseModel):
    bill_ids: list[str]
