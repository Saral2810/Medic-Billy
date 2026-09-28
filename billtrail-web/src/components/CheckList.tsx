import type { CheckResult } from "@/types/bill";

const icon = { pass: ["✓", "text-ok"], warning: ["!", "text-warn"], needs_review: ["✕", "text-bad"] } as const;

export default function CheckList({ checks }: { checks: CheckResult[] }) {
  return (
    <ul className="divide-y divide-line">
      {checks.map((c) => {
        const [sym, cls] = icon[c.severity];
        return (
          <li key={c.id} className="flex gap-3 py-2 text-sm">
            <span className={`w-4 text-center font-semibold ${cls}`} aria-hidden>{sym}</span>
            <div>
              <span className="sr-only">{c.severity === "pass" ? "Passed: " : c.severity === "warning" ? "Warning: " : "Failed: "}</span>
              {c.label}
              {c.detail && <p className="text-xs text-muted">{c.detail}</p>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
