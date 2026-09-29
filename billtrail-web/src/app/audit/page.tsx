"use client";
import { useEffect, useState } from "react";
import { api, isMock } from "@/lib/api";
import type { AuditEntry } from "@/types/bill";
import { stamp } from "@/lib/format";
import { SkeletonRows } from "@/components/Skeleton";
import EmptyState from "@/components/EmptyState";

const label: Record<AuditEntry["action"], string> = {
  uploaded: "Bill uploaded", ai_read: "Read by the model", corrected: "Corrected by a person", viewed: "Viewed", exported: "Exported in a claim bundle",
};

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ ok: boolean; brokenAt?: number } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.listAudit().then((e) => setEntries([...e].reverse())).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function check() { setBusy(true); try { setResult(await api.verifyChain()); } finally { setBusy(false); } }

  if (error) return <p role="alert" className="text-bad">{error}</p>;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-2 flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Paper trail</h1>
        <button className="btn btn-primary ml-auto" onClick={check} disabled={busy || !entries?.length}>{busy ? "Checking…" : "Check the chain"}</button>
        {isMock && <button className="btn btn-ghost" onClick={async () => { api.tamperDemo(); await load(); setResult(null); }}>Simulate tampering</button>}
      </div>
      <p className="mb-5 text-muted">Every action on every bill, newest first. Each entry is linked to the one before it, so an edited entry breaks the chain.</p>

      {result && (
        <div role="status" className={`mb-5 rounded-md border px-4 py-3 text-sm ${result.ok ? "border-ok/30 bg-ok/5 text-ok" : "border-bad/30 bg-bad/5 text-bad"}`}>
          {result.ok ? "The chain is intact. No entry has been changed." : `The chain breaks at entry #${result.brokenAt}. That entry or an earlier one was altered.`}
        </div>
      )}

      {!entries ? (
        <SkeletonRows rows={5} cols={3} />
      ) : entries.length === 0 ? (
        <EmptyState title="No history yet" body="Actions on your bills will be recorded here." action={{ href: "/upload", label: "Add a bill" }} />
      ) : (
        <ol className="card divide-y divide-line">
          {entries.map((e) => (
            <li key={e.seq} className={`flex flex-wrap gap-x-4 gap-y-1 p-4 text-sm ${result && !result.ok && e.seq === result.brokenAt ? "bg-bad/5" : ""}`}>
              <span className="w-10 shrink-0 text-muted">#{e.seq}</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{label[e.action]}</p>
                <p className="text-muted">Bill {e.billId} by {e.actor}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-muted" title={e.hash}>{e.hash}</p>
              </div>
              <time className="shrink-0 text-muted" dateTime={e.at}>{stamp(e.at)}</time>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
