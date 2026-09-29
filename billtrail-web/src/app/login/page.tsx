"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      signIn(mode === "in" ? await api.login(email, password) : await api.register(name, email, password));
      router.replace("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally { setBusy(false); }
  }

  const field = (label: string, value: string, set: (v: string) => void, type = "text", auto = "") => (
    <label className="block">
      <span className="mb-1 block text-sm">{label}</span>
      <input className="input" type={type} value={value} autoComplete={auto} required onChange={(e) => set(e.target.value)} />
    </label>
  );

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">{mode === "in" ? "Sign in" : "Create your account"}</h1>
      <p className="mb-6 text-sm text-muted">{mode === "in" ? "Your bills stay private to you." : "Use at least 8 characters for the password."}</p>
      <form onSubmit={submit} className="card space-y-4 p-5">
        {mode === "up" && field("Full name", name, setName, "text", "name")}
        {field("Email", email, setEmail, "email", "email")}
        {field("Password", password, setPassword, "password", mode === "in" ? "current-password" : "new-password")}
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : mode === "in" ? "Sign in" : "Create account"}</button>
      </form>
      <button className="mt-4 text-sm text-accent hover:underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); setError(""); }}>
        {mode === "in" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
