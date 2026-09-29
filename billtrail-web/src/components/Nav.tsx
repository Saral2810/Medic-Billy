"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { isMock } from "@/lib/api";
import { useAuth } from "./AuthProvider";

const base = [["/upload", "Add a bill"], ["/bills", "Bills"], ["/emergency", "Emergency lookup"], ["/audit", "Paper trail"]] as const;

export default function Nav() {
  const path = usePathname();
  const { user, signOut } = useAuth();
  const links = user?.role === "admin" ? [...base, ["/users", "Users"] as const] : base;
  return (
    <header className="border-b border-line bg-panel print:hidden">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 py-3">
        <Link href="/upload" className="text-lg font-semibold tracking-tight text-accent">BillTrail</Link>
        {user && (
          <nav className="flex gap-1">
            {links.map(([href, label]) => (
              <Link key={href} href={href}
                className={`rounded-md px-3 py-1.5 text-sm ${path.startsWith(href) ? "bg-accent/10 font-medium text-accent" : "text-muted hover:text-ink"}`}>
                {label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-sm">
          {isMock && <span className="rounded bg-warn/10 px-2 py-0.5 text-xs text-warn">Demo data</span>}
          {user && !isMock && (
            <>
              <span>{user.name} <span className="ml-1 rounded bg-accent/10 px-1.5 py-0.5 text-xs capitalize text-accent">{user.role}</span></span>
              <button className="btn btn-ghost !px-2.5 !py-1" onClick={signOut}>Sign out</button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
