import type { AuditEntry, Bill } from "@/types/bill";
import { mock } from "./mock";
import { verifyChain } from "./audit";
import { toFhirBundle } from "./fhir";
import { fromApi, toStandard, type ApiBill } from "./adapter";

// Empty NEXT_PUBLIC_API_URL = mock data. Set it (e.g. http://localhost:8000) to use the FastAPI backend.
const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const isMock = !BASE;

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try { r = await fetch(`${BASE}${path}`, init); }
  catch { throw new Error("Cannot reach the server. Is the backend running?"); }
  if (!r.ok) {
    const text = await r.text();
    let msg: unknown = text;
    try { msg = JSON.parse(text).detail; } catch { /* not JSON */ }
    throw new Error(typeof msg === "string" && msg ? msg : `Request failed (${r.status})`);
  }
  return r.json();
}

const asBill = (a: ApiBill) => fromApi(a, BASE!);
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  listBills: (): Promise<Bill[]> => (isMock ? mock.listBills() : http<ApiBill[]>("/bills").then((r) => r.map(asBill))),
  getBill: (id: string): Promise<Bill> => (isMock ? mock.getBill(id) : http<ApiBill>(`/bills/${id}`).then(asBill)),
  uploadBill: (file: File): Promise<Bill> => {
    if (isMock) return mock.uploadBill(file);
    const fd = new FormData(); fd.append("file", file);
    return http<ApiBill>("/bills", { method: "POST", body: fd }).then(asBill);
  },
  updateBill: (b: Bill): Promise<Bill> =>
    isMock ? mock.updateBill(b) : http<ApiBill>(`/bills/${b.id}`, { ...json(toStandard(b)), method: "PUT" }).then(asBill),
  exportClaim: (ids: string[], bills: Bill[]): Promise<unknown> =>
    isMock ? Promise.resolve(toFhirBundle(bills.filter((b) => ids.includes(b.id)))) : http("/claims", json({ bill_ids: ids })),
  listAudit: (): Promise<AuditEntry[]> => (isMock ? mock.listAudit() : http("/audit")),
  verifyChain: async (): Promise<{ ok: boolean; brokenAt?: number }> =>
    isMock ? verifyChain(await mock.listAudit()) : http("/audit/verify"),
  tamperDemo: () => mock.tamper(),
};
