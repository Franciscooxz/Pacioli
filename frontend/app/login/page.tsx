"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error de acceso");
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-canvas p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-card">
        <div className="mb-6 text-center">
          <div className="text-2xl font-extrabold text-ink">
            Conta<span className="text-primary">flow</span>
          </div>
          <p className="mt-1 text-sm text-ink-muted">Ingresa a tu cuenta</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-ink">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              className="h-11 w-full rounded-lg border border-line bg-canvas px-3.5 text-sm outline-none focus:border-primary"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-ink">
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="h-11 w-full rounded-lg border border-line bg-canvas px-3.5 text-sm outline-none focus:border-primary"
            />
          </div>

          {err && (
            <div className="rounded-lg bg-danger/10 px-3 py-2 text-sm font-medium text-danger">
              {err}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="h-11 w-full rounded-lg bg-primary text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-60"
          >
            {busy ? "Verificando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
