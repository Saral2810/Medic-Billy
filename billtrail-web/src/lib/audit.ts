import type { AuditEntry } from "@/types/bill";
import { sha256Hex } from "./hash";

export const GENESIS = "GENESIS";
export const hashEntry = (e: Omit<AuditEntry, "hash">) =>
  sha256Hex([e.prevHash, e.seq, e.action, e.billId, e.actor, e.at].join("|"));

export async function verifyChain(entries: AuditEntry[]): Promise<{ ok: boolean; brokenAt?: number }> {
  let prev = GENESIS;
  for (const e of entries) {
    if (e.prevHash !== prev || (await hashEntry(e)) !== e.hash) return { ok: false, brokenAt: e.seq };
    prev = e.hash;
  }
  return { ok: true };
}
