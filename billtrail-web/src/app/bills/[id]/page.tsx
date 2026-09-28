"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Bill } from "@/types/bill";
import OriginalViewer from "@/components/OriginalViewer";
import BillEditor from "@/components/BillEditor";
import CheckList from "@/components/CheckList";
import StatusBadge from "@/components/StatusBadge";

export default function BillDetail() {
  const { id } = useParams<{ id: string }>();
  const [bill, setBill] = useState<Bill | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.getBill(id).then(setBill).catch((e) => setError(e.message)); }, [id]);

  if (error) return <p role="alert" className="text-bad">{error}. <Link className="underline" href="/bills">Back to bills</Link></p>;
  if (!bill) return <p className="text-muted" role="status">Loading bill…</p>;

  return (
    <div>
      <div className="mb-5 flex items-center gap-3">
        <Link href="/bills" className="text-sm text-muted hover:text-ink">Bills</Link><span className="text-muted">/</span>
        <h1 className="text-2xl font-semibold tracking-tight">{bill.invoiceNumber || bill.fileName}</h1>
        <StatusBadge status={bill.status} />
        {bill.reviewedBy && <span className="text-xs text-muted">Reviewed by {bill.reviewedBy}</span>}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="lg:sticky lg:top-6 lg:self-start"><OriginalViewer url={bill.fileUrl} type={bill.fileType} name={bill.fileName} /></div>
        <div className="space-y-6">
          <section className="card p-4"><h2 className="mb-2 font-medium">Checks</h2><CheckList checks={bill.checks} /></section>
          <BillEditor key={bill.status + bill.checks.length} bill={bill} saving={saving}
            onSave={async (b) => { setSaving(true); try { setBill(await api.updateBill(b)); } finally { setSaving(false); } }} />
        </div>
      </div>
    </div>
  );
}
