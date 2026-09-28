"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Bill } from "@/types/bill";
import Dropzone from "@/components/Dropzone";
import OriginalViewer from "@/components/OriginalViewer";
import BillEditor from "@/components/BillEditor";
import CheckList from "@/components/CheckList";
import StatusBadge from "@/components/StatusBadge";

type Phase = "idle" | "processing" | "done" | "error";

export default function UploadPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [bill, setBill] = useState<Bill | null>(null);
  const [file, setFile] = useState<{ url: string; type: string; name: string } | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => () => clearInterval(timer.current), []);

  async function handleFile(f: File) {
    setError(""); setFile({ url: URL.createObjectURL(f), type: f.type, name: f.name }); setPhase("processing");
    try {
      const created = await api.uploadBill(f);
      timer.current = setInterval(async () => {
        const b = await api.getBill(created.id);
        if (b.status !== "processing") { clearInterval(timer.current); setBill(b); setPhase("done"); }
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Try again."); setPhase("idle"); setFile(null);
    }
  }

  async function save(b: Bill) {
    setSaving(true);
    try { setBill(await api.updateBill(b)); } finally { setSaving(false); }
  }

  function reset() { clearInterval(timer.current); setBill(null); setFile(null); setPhase("idle"); }

  if (phase === "idle") {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Add a bill</h1>
        <p className="mb-6 text-muted">Upload a pharmacy, lab or hospital bill. We read it, check it, and keep the original untouched.</p>
        <Dropzone onFile={handleFile} error={error} />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{phase === "done" ? "Review the details" : "Reading your bill"}</h1>
        {bill && phase === "done" && <StatusBadge status={bill.status} />}
        <div className="ml-auto flex gap-2">
          {bill && <Link href={`/bills/${bill.id}`} className="btn btn-ghost">Open in Bills</Link>}
          <button className="btn btn-ghost" onClick={reset}>Add another bill</button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="lg:sticky lg:top-6 lg:self-start">{file && <OriginalViewer {...file} />}</div>

        {phase === "processing" && (
          <div className="card flex flex-col items-center justify-center gap-3 p-12 text-center" role="status">
            <span className="size-8 animate-spin rounded-full border-2 border-line border-t-accent motion-reduce:animate-none" />
            <p className="font-medium">Processing…</p>
            <p className="text-sm text-muted">You can leave this page. The bill will appear under Bills when it is ready.</p>
          </div>
        )}

        {phase === "done" && bill && (
          <div className="space-y-6">
            <section className="card p-4">
              <div className="mb-2 flex items-baseline justify-between">
                <h2 className="font-medium">Checks</h2>
                <span className="text-xs text-muted">Model confidence {Math.round(bill.confidence * 100)}%</span>
              </div>
              <CheckList checks={bill.checks} />
              <p className="mt-3 break-all font-mono text-[11px] text-muted">SHA-256 {bill.sha256}</p>
            </section>
            {bill.status === "failed"
              ? <p role="alert" className="card p-4 text-bad">{bill.error || "The bill could not be read."}</p>
              : <BillEditor key={bill.checks.map((c) => c.severity).join() + bill.status} bill={bill} onSave={save} saving={saving} />}
          </div>
        )}
      </div>
    </div>
  );
}
