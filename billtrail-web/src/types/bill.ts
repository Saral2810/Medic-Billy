export type BillStatus = "processing" | "verified" | "needs_review" | "failed";
export type Severity = "pass" | "warning" | "needs_review";

export interface BillItem {
  name: string; hsn: string; batch: string; expiry: string; // YYYY-MM-DD
  qty: number; mrp: number; rate: number; discount: number; amount: number;
}
export interface CheckResult { id: string; label: string; passed: boolean; severity: Severity; detail?: string }
export interface Bill {
  id: string; status: BillStatus;
  fileName: string; fileUrl: string; fileType: string; sha256: string; uploadedAt: string;
  confidence: number;            // 0..1 from the model
  unreadable: string[];          // e.g. "pharmacy.gstin", "items.2.batch"
  reviewedBy?: string; error?: string; owner?: string;
  pharmacy: { name: string; address: string; gstin: string; drugLicence: string; phone: string };
  invoiceNumber: string; invoiceDate: string; billType: "pharmacy" | "lab" | "hospital";
  patientName: string; doctorName: string;
  items: BillItem[];
  tax: { rate: number; cgst: number; sgst: number; igst: number };
  totals: { subTotal: number; discount: number; totalTax: number; grandTotal: number };
  checks: CheckResult[];
}
export interface AuditEntry {
  seq: number; action: "uploaded" | "ai_read" | "corrected" | "viewed" | "exported";
  billId: string; actor: string; at: string; prevHash: string; hash: string;
}

export type Role = "patient" | "reviewer" | "admin";
export interface User { id: string; email: string; name: string; role: Role }
