"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import type { Role, User } from "@/types/bill";

const notes: Record<Role, string> = {
  patient: "Sees and edits only their own bills.",
  reviewer: "Sees and corrects everyone's bills.",
  admin: "Reviewer access, plus manages these roles.",
};

export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { if (me?.role === "admin") api.listUsers().then(setUsers).catch((e) => setError(e.message)); }, [me]);

  if (me?.role !== "admin") return <p className="text-muted">Only admins can manage users.</p>;
  if (!users) return <p className="text-muted" role="status">{error || "Loading users…"}</p>;

  async function change(u: User, role: Role) {
    setError("");
    try { const next = await api.setRole(u.id, role); setUsers((p) => p!.map((x) => (x.id === u.id ? next : x))); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not change the role."); }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Users</h1>
      <p className="mb-5 text-muted">New accounts start as patients. Promote someone to reviewer to let them check everyone&apos;s bills.</p>
      {error && <p role="alert" className="mb-3 text-sm text-bad">{error}</p>}
      <ul className="card divide-y divide-line">
        {users.map((u) => (
          <li key={u.id} className="flex flex-wrap items-center gap-3 p-4 text-sm">
            <div className="min-w-0 flex-1"><p className="font-medium">{u.name}{u.id === me.id && " (you)"}</p><p className="text-muted">{u.email}</p></div>
            <div className="text-right">
              <select className="input w-auto capitalize" aria-label={`Role for ${u.name}`} value={u.role} disabled={u.id === me.id}
                onChange={(e) => change(u, e.target.value as Role)}>
                <option value="patient">patient</option><option value="reviewer">reviewer</option><option value="admin">admin</option>
              </select>
              <p className="mt-1 text-xs text-muted">{notes[u.role]}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
