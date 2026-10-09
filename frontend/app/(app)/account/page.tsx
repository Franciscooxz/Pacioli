"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthError, changePassword, clearToken, getMe } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState(false);

  const onAuthError = useCallback(
    (e: unknown) => {
      if (e instanceof AuthError) {
        clearToken();
        router.replace("/login");
        return true;
      }
      return false;
    },
    [router],
  );

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch((e) => {
        onAuthError(e);
      });
  }, [onAuthError]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    setOk(false);
    if (next.length < 8) {
      setErr("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (next !== confirm) {
      setErr("La confirmación no coincide con la nueva contraseña.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      setOk(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (e) {
      if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "No se pudo cambiar");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-extrabold text-ink">Mi cuenta</h1>

      <section className="rounded-card bg-white p-6 shadow-card">
        <div className="mb-4">
          <div className="text-xs font-bold uppercase tracking-wide text-ink-muted">Correo</div>
          <div className="text-sm font-semibold text-ink">{me?.email ?? "…"}</div>
        </div>
        <div>
          <div className="text-xs font-bold uppercase tracking-wide text-ink-muted">Rol</div>
          <div className="text-sm font-semibold text-ink">{me?.role ?? "…"}</div>
        </div>
      </section>

      <section className="rounded-card bg-white p-6 shadow-card">
        <h2 className="mb-4 text-lg font-extrabold text-ink">Cambiar contraseña</h2>
        <form onSubmit={submit} className="space-y-4">
          <Password label="Contraseña actual" value={current} onChange={setCurrent} />
          <Password label="Nueva contraseña" value={next} onChange={setNext} />
          <Password label="Confirmar nueva contraseña" value={confirm} onChange={setConfirm} />

          {err && <p className="text-sm font-semibold text-danger">{err}</p>}
          {ok && <p className="text-sm font-semibold text-success">Contraseña actualizada.</p>}

          <button
            type="submit"
            disabled={busy || !current || !next || !confirm}
            className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-40"
          >
            {busy ? "Guardando…" : "Actualizar contraseña"}
          </button>
        </form>
      </section>
    </div>
  );
}

function Password({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-bold uppercase tracking-wide text-ink-muted">
        {label}
      </span>
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
      />
    </label>
  );
}
