import type { BillStatus } from "@/types/bill";

const map: Record<BillStatus, [string, string]> = {
  verified: ["Verified", "bg-ok/10 text-ok"],
  needs_review: ["Needs review", "bg-warn/10 text-warn"],
  processing: ["Processing", "bg-accent/10 text-accent"],
  failed: ["Failed", "bg-bad/10 text-bad"],
};

export default function StatusBadge({ status }: { status: BillStatus }) {
  const [label, cls] = map[status];
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}
