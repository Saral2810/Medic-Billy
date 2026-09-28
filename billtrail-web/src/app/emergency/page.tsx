"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Bill } from "@/types/bill";
import { day } from "@/lib/format";

interface Row { name: string; last: string; times: number; doctors: Set<string>; pharmacies: Set<string>; unverified: boolean }
const key = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");

export default function EmergencyLookup() {
  const [bills, setBills] = useState<Bill[] | null>(null);
  const [q, setQ] = useState("");
  const [patient, setPatient] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => { api.listBills().then(setBills); }, []);

  const patients = useMemo(
    () => [...new Set((bills ?? []).map((b) => b.patientName.trim()).filter(Boolean))].sort(),
    [bills]);
  const shown = patients.filter((p) => !q.trim() || key(p).includes(key(q)));

  const { rows, used } = useMemo(() => {
    const used = (bills ?? []).filter((b) => patient && key(b.patientName) === key(patient) &&
      (b.status === "verified" || (unverified && b.status === "needs_review")));
    const map = new Map<string, Row>();
    for (const b of used) for (const it of b.items) {
      if (!it.name.trim()) continue;
      const r = map.get(key(it.name)) ?? { name: it.name.trim(), last: "", times: 0, doctors: new Set(), pharmacies: new Set(), unverified: true };
      r.times += 1;
      if (b.invoiceDate > r.last) r.last = b.invoiceDate;
      if (b.doctorName.trim()) r.doctors.add(b.doctorName.trim());
      if (b.pharmacy.name.trim()) r.pharmacies.add(b.pharmacy.name.trim());
      if (b.status === "verified") r.unverified = false;
      map.set(key(it.name), r);
    }
    return { rows: [...map.values()].sort((a, b) => b.last.localeCompare(a.last)), used };
  }, [bills, patient, unverified]);

  async function copy() {
    const text = `Medicines bought by ${patient} (from ${used.length} bills)\n` +
      rows.map((r) => `- ${r.name}: last ${day(r.last)}, bought ${r.times}x${r.doctors.size ? `, prescribed by ${[...r.doctors].join(", ")}` : ""}`).join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  }

  if (!bills) return <p className="text-muted" role="status">Loading…</p>;

  return (
    <div>
      <div className="print:hidden">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Emergency lookup</h1>
        <p className="mb-5 max-w-2xl text-muted">Pick a patient to see every medicine on their saved bills. Useful when someone cannot say what they take.</p>

        <input className="input max-w-sm" placeholder="Search patient name" aria-label="Search patient" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="mt-3 flex flex-wrap gap-2">
          {shown.map((p) => (
            <button key={p} onClick={() => setPatient(p)} aria-pressed={p === patient}
              className={`btn ${p === patient ? "btn-primary" : "btn-ghost"}`}>{p}</button>
          ))}
          {patients.length === 0 && <p className="text-sm text-muted">No patient names yet. Add a bill first.</p>}
          {patients.length > 0 && shown.length === 0 && <p className="text-sm text-muted">No patient matches “{q}”.</p>}
        </div>
      </div>

      {patient && (
        <section className="mt-8">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <div>
              <h2 className="text-xl font-semibold">{patient}</h2>
              <p className="text-sm text-muted">{rows.length} medicines from {used.length} {unverified ? "bills" : "verified bills"}</p>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-3 print:hidden">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={unverified} onChange={(e) => setUnverified(e.target.checked)} /> Include bills that need review
              </label>
              <button className="btn btn-ghost" onClick={copy} disabled={rows.length === 0}>{copied ? "Copied" : "Copy list"}</button>
              <button className="btn btn-primary" onClick={() => window.print()} disabled={rows.length === 0}>Print</button>
            </div>
          </div>

          {rows.length === 0 ? (
            <p className="card p-6 text-sm text-muted">No verified bills for this patient. Tick “Include bills that need review” to see unchecked ones.</p>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="border-b border-line text-left text-xs text-muted">
                  <tr><th className="p-3 font-normal">Medicine</th><th className="p-3 font-normal">Last bought</th><th className="p-3 font-normal">Times</th>
                    <th className="p-3 font-normal">Prescribed by</th><th className="p-3 font-normal">Pharmacy</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.name} className="border-b border-line last:border-0">
                      <td className="p-3 font-medium">{r.name}{r.unverified && <span className="ml-2 rounded bg-warn/10 px-1.5 py-0.5 text-xs font-normal text-warn">Unverified</span>}</td>
                      <td className="p-3">{day(r.last)}</td><td className="p-3">{r.times}</td>
                      <td className="p-3">{[...r.doctors].join(", ") || "-"}</td><td className="p-3">{[...r.pharmacies].join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-4 text-xs text-muted">Built from purchase records only. It may be incomplete, it does not show doses, and it is not a prescription list. Confirm with the patient or their doctor.</p>
        </section>
      )}
    </div>
  );
}
