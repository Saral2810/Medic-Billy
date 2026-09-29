"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, isMock, type Session } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth";
import type { User } from "@/types/bill";

const DEMO: User = { id: "demo", name: "Demo user", email: "demo@example.com", role: "admin" };
interface Ctx { user: User | null; signIn: (s: Session) => void; signOut: () => void }
const AuthContext = createContext<Ctx>({ user: null, signIn: () => {}, signOut: () => {} });
export const useAuth = () => useContext(AuthContext);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(isMock ? DEMO : null);
  const [ready, setReady] = useState(isMock);
  const path = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isMock) return;
    if (!getToken()) { setReady(true); return; }
    api.me().then(setUser).catch(() => clearToken()).finally(() => setReady(true));
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!user && path !== "/login") router.replace("/login");
    if (user && path === "/login") router.replace("/upload");
  }, [ready, user, path, router]);

  const signIn = (s: Session) => { setToken(s.token); setUser(s.user); };
  const signOut = () => { clearToken(); setUser(null); router.replace("/login"); };

  if (!ready || (!user && path !== "/login")) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center" role="status">
        <span className="size-6 animate-spin rounded-full border-2 border-line border-t-accent motion-reduce:animate-none" />
      </div>
    );
  }
  return <AuthContext.Provider value={{ user, signIn, signOut }}>{children}</AuthContext.Provider>;
}
