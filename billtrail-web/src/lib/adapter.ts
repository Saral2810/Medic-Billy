import type { Bill } from "@/types/bill";

// Shapes returned by FastAPI (billtrail-ml/backend/app/schemas.py). Numbers and strings can be null.
type N = number | null; type S = string | null;
export interface StandardBill {
  bill_type: "pharmacy" | "lab" | "hospital" | null;
  seller: { name: S; address: S; gstin: S; drug_licence_no: S; phone: S };
  invoice: { number: S; date: S };
  patient_name: S; doctor_name: S;
  items: { name: S; hsn: S; batch: S; expiry: S; qty: N; mrp: N; rate: N; discount: N; amount: N }[];
  tax: { gst_rate: N; cgst: N; sgst: N; igst: N };
  totals: { subtotal: N; discount: N; taxable_value: N; total_tax: N; grand_total: N };
  confidence: N; unreadable: string[];
}
export interface ApiBill {
  id: string; status: "processing" | "verified" | "review" | "failed";
  file_name: string; content_type: string; sha256: string; uploaded_at: string;
  reviewed_by: string | null; error: string | null;
  bill: StandardBill; checks: { code: string; label: string; status: "pass" | "warn" | "fail"; detail: string }[];
}

const n = (v: N | undefined) => v ?? 0;
const s = (v: S | undefined) => v ?? "";
const z = (v: number) => (v === 0 ? null : v);   // 0 in the form means "not on the bill"
const t = (v: string) => v.trim() || null;

// The model names unreadable fields in backend style; the form uses these keys.
const KEYS: Record<string, string> = {
  "seller.name": "pharmacy.name", "seller.gstin": "pharmacy.gstin", "seller.address": "pharmacy.address",
  "totals.grand_total": "totals.grandTotal", "totals.subtotal": "totals.subTotal", "totals.total_tax": "totals.totalTax",
};

export function fromApi(a: ApiBill, base: string): Bill {
  const b = a.bill;
  return {
    id: a.id, status: a.status === "review" ? "needs_review" : a.status,
    fileName: a.file_name, fileUrl: `${base}/bills/${a.id}/file`, fileType: a.content_type, sha256: a.sha256, uploadedAt: a.uploaded_at,
    confidence: b.confidence ?? 1, unreadable: b.unreadable.map((k) => KEYS[k] ?? k),
    reviewedBy: a.reviewed_by ?? undefined, error: a.error ?? undefined,
    pharmacy: { name: s(b.seller.name), address: s(b.seller.address), gstin: s(b.seller.gstin), drugLicence: s(b.seller.drug_licence_no), phone: s(b.seller.phone) },
    invoiceNumber: s(b.invoice.number), invoiceDate: s(b.invoice.date), billType: b.bill_type ?? "pharmacy",
    patientName: s(b.patient_name), doctorName: s(b.doctor_name),
    items: b.items.map((i) => ({ name: s(i.name), hsn: s(i.hsn), batch: s(i.batch), expiry: s(i.expiry), qty: n(i.qty), mrp: n(i.mrp), rate: n(i.rate), discount: n(i.discount), amount: n(i.amount) })),
    tax: { rate: n(b.tax.gst_rate), cgst: n(b.tax.cgst), sgst: n(b.tax.sgst), igst: n(b.tax.igst) },
    totals: { subTotal: n(b.totals.subtotal), discount: n(b.totals.discount), totalTax: n(b.totals.total_tax), grandTotal: n(b.totals.grand_total) },
    checks: a.checks.map((c) => ({
      id: c.code, label: c.label, passed: c.status === "pass", detail: c.detail,
      severity: c.status === "pass" ? "pass" : c.status === "warn" ? "warning" : "needs_review",
    })),
  };
}

export function toStandard(b: Bill): StandardBill {
  return {
    bill_type: b.billType,
    seller: { name: t(b.pharmacy.name), address: t(b.pharmacy.address), gstin: t(b.pharmacy.gstin), drug_licence_no: t(b.pharmacy.drugLicence), phone: t(b.pharmacy.phone) },
    invoice: { number: t(b.invoiceNumber), date: t(b.invoiceDate) },
    patient_name: t(b.patientName), doctor_name: t(b.doctorName),
    items: b.items.map((i) => ({ name: t(i.name), hsn: t(i.hsn), batch: t(i.batch), expiry: t(i.expiry), qty: z(i.qty), mrp: z(i.mrp), rate: z(i.rate), discount: z(i.discount), amount: z(i.amount) })),
    tax: { gst_rate: z(b.tax.rate), cgst: z(b.tax.cgst), sgst: z(b.tax.sgst), igst: z(b.tax.igst) },
    totals: { subtotal: z(b.totals.subTotal), discount: z(b.totals.discount), taxable_value: null, total_tax: z(b.totals.totalTax), grand_total: z(b.totals.grandTotal) },
    confidence: b.confidence, unreadable: [],
  };
}
