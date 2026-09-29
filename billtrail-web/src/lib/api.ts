import type { AuditEntry, Bill, Role, User } from "@/types/bill";
import { mock } from "./mock";
import { verifyChain } from "./audit";
import { toFhirBundle } from "./fhir";
import { fromApi, toStandard, type ApiBill } from "./adapter";
import { authHeader, clearToken } from "./auth";

// Empty NEXT_PUBLIC_API_URL = mock data (no login). Set it (e.g. http://localhost:8000) to use the FastAPI backend.
const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const isMock = !BASE;
export interface Session { token: string; user: User }

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try { r = await fetch(`${BASE}${path}`, { ...init, headers: { ...authHeader(), ...(init?.headers as Record<string, string>) } }); }
  catch { throw new Error("Cannot reach the server. Is the backend running?"); }
  if (!r.ok) {
    if (r.status === 401 && !path.startsWith("/auth/login") && typeof window !== "undefined" && location.pathname !== "/login") {
      clearToken(); window.location.href = "/login";
    }
    const text = await r.text();
    let msg: unknown = text;
    try { msg = JSON.parse(text).detail; } catch { /* not JSON */ }
    throw new Error(typeof msg === "string" && msg ? msg : `Request failed (${r.status})`);
  }
  return r.json();
}

const asBill = (a: ApiBill) => fromApi(a, BASE!);
const send = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  login: (email: string, password: string) => http<Session>("/auth/login", send("POST", { email, password })),
  register: (name: string, email: string, password: string) => http<Session>("/auth/register", send("POST", { name, email, password })),
  me: () => http<User>("/auth/me"),
  listUsers: (): Promise<User[]> => (isMock ? Promise.resolve([]) : http("/users")),
  setRole: (id: string, role: Role) => http<User>(`/users/${id}/role`, send("PUT", { role })),

  listBills: (): Promise<Bill[]> => (isMock ? mock.listBills() : http<ApiBill[]>("/bills").then((r) => r.map(asBill))),
  getBill: (id: string): Promise<Bill> => (isMock ? mock.getBill(id) : http<ApiBill>(`/bills/${id}`).then(asBill)),
  uploadBill: (file: File): Promise<Bill> => {
    if (isMock) return mock.uploadBill(file);
    const fd = new FormData(); fd.append("file", file);
    return http<ApiBill>("/bills", { method: "POST", body: fd }).then(asBill);
  },
  updateBill: (b: Bill): Promise<Bill> =>
    isMock ? mock.updateBill(b) : http<ApiBill>(`/bills/${b.id}`, send("PUT", toStandard(b))).then(asBill),
  exportClaim: (ids: string[], bills: Bill[]): Promise<unknown> =>
    isMock ? Promise.resolve(toFhirBundle(bills.filter((b) => ids.includes(b.id)))) : http("/claims", send("POST", { bill_ids: ids })),
  listAudit: (): Promise<AuditEntry[]> => (isMock ? mock.listAudit() : http("/audit")),
  verifyChain: async (): Promise<{ ok: boolean; brokenAt?: number }> =>
    isMock ? verifyChain(await mock.listAudit()) : http("/audit/verify"),
  tamperDemo: () => mock.tamper(),
};
