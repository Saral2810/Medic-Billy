import type { Bill, CheckResult, BillStatus } from "@/types/bill";
import { isValidGstin } from "./gstin";

const near = (a: number, b: number, tol = 1) => Math.abs(a - b) <= tol;

/** Mirrors Section 6 of the proposal. Re-run after every human correction. */
export function runChecks(b: Bill): CheckResult[] {
  const out: CheckResult[] = [];
  const add = (id: string, label: string, ok: boolean, fail: "needs_review" | "warning", detail?: string) =>
    out.push({ id, label, passed: ok, severity: ok ? "pass" : fail, detail: ok ? undefined : detail });

  const missing = [
    !b.pharmacy.name && "seller name", !b.pharmacy.address && "seller address", !b.pharmacy.gstin && "GSTIN",
    !b.invoiceNumber && "invoice number", !b.invoiceDate && "date", b.items.length === 0 && "item lines",
  ].filter(Boolean);
  add("required", "Required details present", missing.length === 0, "needs_review", `Missing: ${missing.join(", ")}`);
  add("gstin", "GSTIN is valid", isValidGstin(b.pharmacy.gstin), "needs_review", "Pattern, state code or check character is wrong");
  add("licence", "Drug licence shown", b.billType !== "pharmacy" || !!b.pharmacy.drugLicence.trim(), "warning", "No drug licence number on the bill");
  add("batch", "Batch and expiry on each medicine", b.items.every((i) => i.batch.trim() && i.expiry), "warning", "Some lines have no batch or expiry");
  add("expired", "No expired medicine sold", b.items.every((i) => !i.expiry || i.expiry.slice(0, 7) >= b.invoiceDate.slice(0, 7)), "needs_review", "A medicine expires before the bill date");

  const sum = b.items.reduce((s, i) => s + i.amount, 0);
  add("sum", "Items add up", near(sum, b.totals.subTotal), "needs_review", `Lines total ${sum.toFixed(2)}, sub-total says ${b.totals.subTotal.toFixed(2)}`);
  const taxable = b.totals.subTotal - b.totals.discount;
  const okTotal = near(b.totals.grandTotal, taxable) || near(b.totals.grandTotal, taxable + b.totals.totalTax);
  add("grand", "Grand total correct", okTotal, "needs_review", `Expected ${taxable.toFixed(2)} or ${(taxable + b.totals.totalTax).toFixed(2)}, got ${b.totals.grandTotal.toFixed(2)}`);
  add("split", "CGST equals SGST", b.tax.igst > 0 || near(b.tax.cgst, b.tax.sgst, 0.05), "warning", "CGST and SGST differ for a within-state sale");
  add("confidence", "Model confidence at least 70%", !!b.reviewedBy || b.confidence >= 0.7, "needs_review", `Model confidence is ${Math.round(b.confidence * 100)}%`);
  return out;
}

export const statusFrom = (c: CheckResult[]): BillStatus =>
  c.some((x) => x.severity === "needs_review") ? "needs_review" : "verified";
