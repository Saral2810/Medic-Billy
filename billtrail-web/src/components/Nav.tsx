"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { isMock } from "@/lib/api";

const links = [["/upload", "Add a bill"], ["/bills", "Bills"], ["/emergency", "Emergency lookup"], ["/audit", "Paper trail"]] as const;

export default function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-line bg-panel print:hidden">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 py-3">
        <Link href="/upload" className="text-lg font-semibold tracking-tight text-accent">BillTrail</Link>
        <nav className="flex gap-1">
          {links.map(([href, label]) => (
            <Link key={href} href={href}
              className={`rounded-md px-3 py-1.5 text-sm ${path.startsWith(href) ? "bg-accent/10 font-medium text-accent" : "text-muted hover:text-ink"}`}>
              {label}
            </Link>
          ))}
        </nav>
        {isMock && <span className="ml-auto rounded bg-warn/10 px-2 py-0.5 text-xs text-warn">Demo data</span>}
      </div>
    </header>
  );
}
