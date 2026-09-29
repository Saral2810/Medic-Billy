import Link from "next/link";

export default function EmptyState({ title, body, action }: { title: string; body: string; action?: { href: string; label: string } }) {
  return (
    <div className="card flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      <p className="max-w-sm text-sm text-muted">{body}</p>
      {action && <Link href={action.href} className="btn btn-primary mt-2">{action.label}</Link>}
    </div>
  );
}
