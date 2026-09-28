import type { AuditEntry, Bill } from "@/types/bill";
import { checkChar } from "./gstin";
import { runChecks, statusFrom } from "./checks";
import { sha256Hex } from "./hash";
import { GENESIS, hashEntry } from "./audit";

const gstin = (p: string) => p + checkChar(p);
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const iso = (daysAgo: number) => new Date(Date.now() - daysAgo * 864e5).toISOString();

function finalize(b: Bill): Bill {
  const checks = runChecks(b);
  return { ...b, checks, status: statusFrom(checks) };
}

const base = (id: string, over: Partial<Bill>): Bill => ({
  id, status: "processing", fileName: "bill.jpg", fileUrl: "", fileType: "image/jpeg", sha256: id.repeat(8),
  uploadedAt: new Date().toISOString(), confidence: 0.9, unreadable: [], checks: [],
  pharmacy: { name: "", address: "", gstin: "", drugLicence: "", phone: "" },
  invoiceNumber: "", invoiceDate: "", billType: "pharmacy", patientName: "", doctorName: "", items: [],
  tax: { rate: 0, cgst: 0, sgst: 0, igst: 0 }, totals: { subTotal: 0, discount: 0, totalTax: 0, grandTotal: 0 },
  ...over,
});

/** What the "model" returns for an upload: wrong grand total + one missing batch, to show the review flow. */
const extracted = (b: Bill): Bill => finalize({
  ...b, confidence: 0.82, unreadable: ["items.2.batch", "totals.grandTotal"],
  pharmacy: { name: "Shree Balaji Medicals", address: "12, Vijay Nagar, Indore, MP 452010", gstin: gstin("23ABCDE1234F1Z"), drugLicence: "MP-IND-20B-1123", phone: "0731 400 2211" },
  invoiceNumber: "SBM/" + Math.floor(1000 + Math.random() * 9000), invoiceDate: new Date().toISOString().slice(0, 10),
  patientName: "Rohan Verma", doctorName: "Dr. A. Sharma",
  items: [
    { name: "Dolo 650 Tab", hsn: "30049099", batch: "DL2391", expiry: "2027-08", qty: 2, mrp: 32, rate: 30, discount: 0, amount: 60 },
    { name: "Azithral 500 Tab", hsn: "30042019", batch: "AZ5521", expiry: "2027-03", qty: 1, mrp: 118.5, rate: 110, discount: 0, amount: 110 },
    { name: "ORS Sachet", hsn: "30049099", batch: "", expiry: "2027-01", qty: 3, mrp: 22, rate: 20, discount: 0, amount: 60 },
  ],
  tax: { rate: 12, cgst: 13.8, sgst: 13.8, igst: 0 },
  totals: { subTotal: 230, discount: 0, totalTax: 27.6, grandTotal: 275.6 },
});

const good = finalize(base("a1b2c3d4", {
  fileName: "sanjeevani-0412.jpg", uploadedAt: iso(6), reviewedBy: "Reviewer",
  pharmacy: { name: "Sanjeevani Medical Store", address: "Sector C, Sudama Nagar, Indore, MP", gstin: gstin("23AAPFU0939F1Z"), drugLicence: "MP-IND-20B-0871", phone: "0731 255 0101" },
  invoiceNumber: "SMS-20418", invoiceDate: iso(6).slice(0, 10), patientName: "Rohan Verma", doctorName: "Dr. R. Joshi",
  items: [
    { name: "Metformin 500 Tab", hsn: "30049099", batch: "MF2210", expiry: "2027-11", qty: 2, mrp: 45, rate: 42, discount: 0, amount: 84 },
    { name: "Pantoprazole 40 Tab", hsn: "30049099", batch: "PN8842", expiry: "2027-06", qty: 1, mrp: 96, rate: 90, discount: 0, amount: 90 },
  ],
  tax: { rate: 5, cgst: 4.35, sgst: 4.35, igst: 0 }, totals: { subTotal: 174, discount: 0, totalTax: 8.7, grandTotal: 182.7 },
}));
const review = { ...extracted(base("e5f6a7b8", { fileName: "balaji-1290.jpg" })), uploadedAt: iso(2) };

let bills: Bill[] = [review, good];
const audit: AuditEntry[] = [];
let seq = 0;
const log = (action: AuditEntry["action"], billId: string, actor: string, at = new Date().toISOString()) =>
  audit.push({ seq: ++seq, action, billId, actor, at, prevHash: "", hash: "" });
[good, review].forEach((b) => { log("uploaded", b.id, "you", b.uploadedAt); log("ai_read", b.id, "worker", b.uploadedAt); });
log("corrected", good.id, "Reviewer", iso(5));

async function seal() {
  for (let i = 0; i < audit.length; i++) {
    if (audit[i].hash) continue;
    audit[i].prevHash = i === 0 ? GENESIS : audit[i - 1].hash;
    audit[i].hash = await hashEntry(audit[i]);
  }
}

export const mock = {
  async listBills() { await wait(200); return [...bills].sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt)); },
  async getBill(id: string) {
    await wait(150);
    const b = bills.find((x) => x.id === id);
    if (!b) throw new Error("Bill not found");
    return b;
  },
  async uploadBill(file: File) {
    const sha = await sha256Hex(await file.arrayBuffer());
    if (bills.some((b) => b.sha256 === sha)) throw new Error("This exact file was already uploaded.");
    const id = sha.slice(0, 8);
    const b = base(id, { fileName: file.name, fileType: file.type, fileUrl: URL.createObjectURL(file), sha256: sha });
    bills = [b, ...bills]; log("uploaded", id, "you");
    setTimeout(() => { bills = bills.map((x) => (x.id === id ? extracted(x) : x)); log("ai_read", id, "worker"); }, 2500);
    return b;
  },
  async updateBill(b: Bill) {
    await wait(300);
    const next = finalize({ ...b, unreadable: [], reviewedBy: "Reviewer" });
    bills = bills.map((x) => (x.id === b.id ? next : x)); log("corrected", b.id, "Reviewer");
    return next;
  },
  async listAudit() { await seal(); return audit.map((e) => ({ ...e })); },
  /** Demo only: edits an old entry without re-hashing, so the chain check fails. */
  tamper() { if (audit[1]) audit[1].actor = "someone-else"; },
};
