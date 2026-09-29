"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Bill, BillStatus } from "@/types/bill";
import StatusBadge from "@/components/StatusBadge";
import { day, inr } from "@/lib/format";
import { downloadJson } from "@/lib/fhir";
import { useAuth } from "@/components/AuthProvider";
import { SkeletonCards, SkeletonRows } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";

export default function BillsPage() {
  const [bills, setBills] = useState<Bill[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<BillStatus | "all">("all");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const { user } = useAuth();
  const staff = user?.role !== "patient";

  useEffect(() => { api.listBills().then(setBills).catch((e) => setError(e.message)); }, []);

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (bills ?? []).filter((b) =>
      (status === "all" || b.status === status) &&
      (!t || [b.pharmacy.name, b.pharmacy.gstin, b.patientName, b.invoiceNumber, ...b.items.map((i) => i.name)].some((s) => s.toLowerCase().includes(t))));
  }, [bills, q, status]);

  if (error) return <p role="alert" className="text-bad">{error}</p>;

  if (!bills) {
    return (
      <div>
        <h1 className="mb-5 text-2xl font-semibold tracking-tight">Bills</h1>
        <div className="mb-6"><SkeletonCards /></div>
        <SkeletonRows rows={5} cols={5} />
      </div>
    );
  }

  const stats = [
    ["Bills", String(bills.length)],
    ["Total amount", inr(bills.reduce((s, b) => s + b.totals.grandTotal, 0))],
    ["GST paid", inr(bills.reduce((s, b) => s + b.totals.totalTax, 0))],
    ["Need review", String(bills.filter((b) => b.status === "needs_review").length)],
  ];
  const toggle = (id: string) => setSel((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  if (bills.length === 0) {
    return (
      <div>
        <h1 className="mb-5 text-2xl font-semibold tracking-tight">Bills</h1>
        <EmptyState title="No bills yet" body="Bills you add will show up here, with checks and totals." action={{ href: "/upload", label: "Add your first bill" }} />
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-5 text-2xl font-semibold tracking-tight">Bills</h1>
      <dl className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([k, v]) => (
          <div key={k} className="card px-4 py-3"><dt className="text-xs text-muted">{k}</dt><dd className="text-xl font-semibold">{v}</dd></div>
        ))}
      </dl>

      <div className="mb-3 flex flex-wrap gap-2">
        <input className="input w-full sm:max-w-sm" placeholder="Search pharmacy, GSTIN, patient, invoice or medicine" aria-label="Search bills" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input w-auto" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value as BillStatus | "all")}>
          <option value="all">All statuses</option><option value="verified">Verified</option><option value="needs_review">Needs review</option>
        </select>
        <button className="btn btn-primary sm:ml-auto" disabled={sel.size === 0}
          onClick={async () => downloadJson("claim-bundle.fhir.json", await api.exportClaim([...sel], bills))}>
          Export claim bundle ({sel.size})
        </button>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No bills match" body="Try clearing the search or filter." />
      ) : (
        <>
          {/* Table: sm and up */}
          <div className="card hidden overflow-x-auto sm:block">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr><th className="w-10 p-3" /><th className="p-3 font-normal">Pharmacy</th><th className="p-3 font-normal">Invoice</th><th className="p-3 font-normal">Date</th>
                  <th className="p-3 font-normal">Patient</th>{staff && <th className="p-3 font-normal">Uploaded by</th>}
                  <th className="p-3 text-right font-normal">Total</th><th className="p-3 font-normal">Status</th></tr>
              </thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.id} className="border-b border-line last:border-0 hover:bg-paper/60">
                    <td className="p-3"><input type="checkbox" aria-label={`Select ${b.invoiceNumber || b.fileName}`} checked={sel.has(b.id)} onChange={() => toggle(b.id)} /></td>
                    <td className="p-3"><div className="font-medium">{b.pharmacy.name || "Reading…"}</div><div className="font-mono text-xs text-muted">{b.pharmacy.gstin}</div></td>
                    <td className="p-3"><Link className="text-accent hover:underline" href={`/bills/${b.id}`}>{b.invoiceNumber || b.fileName}</Link></td>
                    <td className="p-3">{day(b.invoiceDate)}</td>
                    <td className="p-3">{b.patientName}</td>
                    {staff && <td className="p-3">{b.owner ?? "-"}</td>}
                    <td className="p-3 text-right">{inr(b.totals.grandTotal)}</td>
                    <td className="p-3"><StatusBadge status={b.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cards: below sm */}
          <ul className="space-y-2 sm:hidden">
            {rows.map((b) => (
              <li key={b.id} className="card flex gap-3 p-3">
                <input type="checkbox" className="mt-1 shrink-0" aria-label={`Select ${b.invoiceNumber || b.fileName}`} checked={sel.has(b.id)} onChange={() => toggle(b.id)} />
                <Link href={`/bills/${b.id}`} className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{b.pharmacy.name || "Reading…"}</span>
                    <StatusBadge status={b.status} />
                  </div>
                  <p className="text-xs text-muted">{b.invoiceNumber || b.fileName} · {day(b.invoiceDate)}</p>
                  <p className="mt-1 text-sm">{b.patientName}{staff && b.owner ? ` · uploaded by ${b.owner}` : ""}</p>
                  <p className="mt-1 font-medium">{inr(b.totals.grandTotal)}</p>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
