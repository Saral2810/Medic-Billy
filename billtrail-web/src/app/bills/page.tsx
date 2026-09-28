"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Bill, BillStatus } from "@/types/bill";
import StatusBadge from "@/components/StatusBadge";
import { day, inr } from "@/lib/format";
import { downloadJson } from "@/lib/fhir";

export default function BillsPage() {
  const [bills, setBills] = useState<Bill[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<BillStatus | "all">("all");
  const [sel, setSel] = useState<Set<string>>(new Set());

  useEffect(() => { api.listBills().then(setBills); }, []);

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (bills ?? []).filter((b) =>
      (status === "all" || b.status === status) &&
      (!t || [b.pharmacy.name, b.pharmacy.gstin, b.patientName, b.invoiceNumber, ...b.items.map((i) => i.name)].some((s) => s.toLowerCase().includes(t))));
  }, [bills, q, status]);

  if (!bills) return <p className="text-muted" role="status">Loading bills…</p>;

  const stats = [
    ["Bills", String(bills.length)],
    ["Total amount", inr(bills.reduce((s, b) => s + b.totals.grandTotal, 0))],
    ["GST paid", inr(bills.reduce((s, b) => s + b.totals.totalTax, 0))],
    ["Need review", String(bills.filter((b) => b.status === "needs_review").length)],
  ];
  const toggle = (id: string) => setSel((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  return (
    <div>
      <h1 className="mb-5 text-2xl font-semibold tracking-tight">Bills</h1>
      <dl className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([k, v]) => (
          <div key={k} className="card px-4 py-3"><dt className="text-xs text-muted">{k}</dt><dd className="text-xl font-semibold">{v}</dd></div>
        ))}
      </dl>

      <div className="mb-3 flex flex-wrap gap-2">
        <input className="input max-w-sm" placeholder="Search pharmacy, GSTIN, patient, invoice or medicine" aria-label="Search bills" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input w-auto" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value as BillStatus | "all")}>
          <option value="all">All statuses</option><option value="verified">Verified</option><option value="needs_review">Needs review</option>
        </select>
        <button className="btn btn-primary ml-auto" disabled={sel.size === 0}
          onClick={async () => downloadJson("claim-bundle.fhir.json", await api.exportClaim([...sel], bills))}>
          Export claim bundle ({sel.size})
        </button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="border-b border-line text-left text-xs text-muted">
            <tr><th className="w-10 p-3" /><th className="p-3 font-normal">Pharmacy</th><th className="p-3 font-normal">Invoice</th><th className="p-3 font-normal">Date</th>
              <th className="p-3 font-normal">Patient</th><th className="p-3 text-right font-normal">Total</th><th className="p-3 font-normal">Status</th></tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id} className="border-b border-line last:border-0 hover:bg-paper/60">
                <td className="p-3"><input type="checkbox" aria-label={`Select ${b.invoiceNumber || b.fileName}`} checked={sel.has(b.id)} onChange={() => toggle(b.id)} /></td>
                <td className="p-3"><div className="font-medium">{b.pharmacy.name || "Reading…"}</div><div className="font-mono text-xs text-muted">{b.pharmacy.gstin}</div></td>
                <td className="p-3"><Link className="text-accent hover:underline" href={`/bills/${b.id}`}>{b.invoiceNumber || b.fileName}</Link></td>
                <td className="p-3">{day(b.invoiceDate)}</td>
                <td className="p-3">{b.patientName}</td>
                <td className="p-3 text-right">{inr(b.totals.grandTotal)}</td>
                <td className="p-3"><StatusBadge status={b.status} /></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={7} className="p-8 text-center text-muted">No bills match. Clear the search or <Link className="text-accent underline" href="/upload">add a bill</Link>.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
