"use client";
import { useState } from "react";
import type { Bill, BillItem } from "@/types/bill";

type P = { label: string; value: string | number; onChange: (v: string) => void; flag?: boolean; type?: string; mono?: boolean };
function F({ label, value, onChange, flag, type = "text", mono }: P) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted">
        {label}{flag && <span className="ml-1.5 text-warn">could not be read, please check</span>}
      </span>
      <input className={`input ${mono ? "font-mono" : ""} ${flag ? "border-warn" : ""}`} type={type}
        step={type === "number" ? "any" : undefined} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

const emptyItem: BillItem = { name: "", hsn: "", batch: "", expiry: "", qty: 1, mrp: 0, rate: 0, discount: 0, amount: 0 };
const n = (v: string) => Number(v) || 0;

export default function BillEditor({ bill, onSave, saving }: { bill: Bill; onSave: (b: Bill) => void; saving?: boolean }) {
  const [d, setD] = useState<Bill>(bill);
  const set = (fn: (x: Bill) => void) => setD((p) => { const x = structuredClone(p); fn(x); return x; });
  const u = (k: string) => d.unreadable.includes(k);

  return (
    <div className="space-y-6">
      <section className="card p-4">
        <h3 className="mb-3 font-medium">Pharmacy</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <F label="Name" value={d.pharmacy.name} flag={u("pharmacy.name")} onChange={(v) => set((x) => { x.pharmacy.name = v; })} />
          <F label="GSTIN" mono value={d.pharmacy.gstin} flag={u("pharmacy.gstin")} onChange={(v) => set((x) => { x.pharmacy.gstin = v.toUpperCase(); })} />
          <F label="Address" value={d.pharmacy.address} onChange={(v) => set((x) => { x.pharmacy.address = v; })} />
          <F label="Drug licence no." value={d.pharmacy.drugLicence} onChange={(v) => set((x) => { x.pharmacy.drugLicence = v; })} />
        </div>
      </section>

      <section className="card p-4">
        <h3 className="mb-3 font-medium">Bill, patient and doctor</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <F label="Invoice number" value={d.invoiceNumber} onChange={(v) => set((x) => { x.invoiceNumber = v; })} />
          <F label="Invoice date" type="date" value={d.invoiceDate} onChange={(v) => set((x) => { x.invoiceDate = v; })} />
          <F label="Patient" value={d.patientName} onChange={(v) => set((x) => { x.patientName = v; })} />
          <F label="Prescribing doctor" value={d.doctorName} onChange={(v) => set((x) => { x.doctorName = v; })} />
        </div>
      </section>

      <section className="card overflow-x-auto p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium">Medicines</h3>
          <button type="button" className="btn btn-ghost" onClick={() => set((x) => { x.items.push({ ...emptyItem }); })}>Add line</button>
        </div>
        <table className="w-full min-w-[820px] text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>{["Item", "HSN", "Batch", "Expiry", "Qty", "MRP", "Rate", "Amount", ""].map((h) => <th key={h} className="pb-2 pr-2 font-normal">{h}</th>)}</tr>
          </thead>
          <tbody>
            {d.items.map((it, i) => {
              const cell = (k: keyof BillItem, type = "text", w = "") => (
                <td className={`pr-2 pb-2 ${w}`}>
                  <input aria-label={`${k} line ${i + 1}`} type={type} step={type === "number" ? "any" : undefined}
                    className={`input ${(u(`items.${i}.${k}`) || (k === "batch" && !it.batch)) ? "border-warn" : ""}`}
                    value={it[k]} onChange={(e) => set((x) => { (x.items[i][k] as string | number) = type === "number" ? n(e.target.value) : e.target.value; })} />
                </td>
              );
              return (
                <tr key={i}>
                  {cell("name", "text", "w-48")}{cell("hsn", "text", "w-28")}{cell("batch", "text", "w-24")}{cell("expiry", "month", "w-36")}
                  {cell("qty", "number", "w-16")}{cell("mrp", "number", "w-20")}{cell("rate", "number", "w-20")}{cell("amount", "number", "w-24")}
                  <td className="pb-2"><button type="button" aria-label={`Remove line ${i + 1}`} className="px-2 text-muted hover:text-bad"
                    onClick={() => set((x) => { x.items.splice(i, 1); })}>✕</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="card p-4">
        <h3 className="mb-3 font-medium">Tax and totals</h3>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <F label="GST rate %" type="number" value={d.tax.rate} onChange={(v) => set((x) => { x.tax.rate = n(v); })} />
          <F label="CGST" type="number" value={d.tax.cgst} onChange={(v) => set((x) => { x.tax.cgst = n(v); })} />
          <F label="SGST" type="number" value={d.tax.sgst} onChange={(v) => set((x) => { x.tax.sgst = n(v); })} />
          <F label="Sub-total" type="number" value={d.totals.subTotal} onChange={(v) => set((x) => { x.totals.subTotal = n(v); })} />
          <F label="Total tax" type="number" value={d.totals.totalTax} onChange={(v) => set((x) => { x.totals.totalTax = n(v); })} />
          <F label="Grand total" type="number" value={d.totals.grandTotal} flag={u("totals.grandTotal")} onChange={(v) => set((x) => { x.totals.grandTotal = n(v); })} />
        </div>
      </section>

      <div className="flex justify-end">
        <button type="button" className="btn btn-primary" disabled={saving} onClick={() => onSave(d)}>
          {saving ? "Saving…" : "Save and re-check"}
        </button>
      </div>
    </div>
  );
}
