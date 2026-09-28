"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthError, clearToken, createUser, getMe, listUsers, updateUser } from "@/lib/api";
import type { AppUser, Role } from "@/lib/types";

export default function UsersPage() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [meId, setMeId] = useState<string | null>(null);
  const [rows, setRows] = useState<AppUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("MEMBER");

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listUsers());
    } catch (e) {
      if (!onAuthError(e)) setErr("No se pudo cargar la lista");
    } finally {
      setLoading(false);
    }
  }, [onAuthError]);

  useEffect(() => {
    getMe()
      .then((me) => {
        setIsAdmin(me.role === "ADMIN");
        setMeId(me.id);
      })
      .catch((e) => {
        if (!onAuthError(e)) setIsAdmin(false);
      });
  }, [onAuthError]);

  useEffect(() => {
    if (isAdmin) void load();
    else if (isAdmin === false) setLoading(false);
  }, [isAdmin, load]);

  const submit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setErr("");
      if (!email.trim() || password.length < 8) {
        setErr("Correo válido y contraseña de al menos 8 caracteres");
        return;
      }
      setBusy(true);
      try {
        await createUser({ email: email.trim(), password, role });
        setEmail("");
        setPassword("");
        setRole("MEMBER");
        await load();
      } catch (e) {
        if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "Error al crear el usuario");
      } finally {
        setBusy(false);
      }
    },
    [email, password, role, load, onAuthError],
  );

  const patch = useCallback(
    async (u: AppUser, body: { role?: Role; active?: boolean }) => {
      setErr("");
      try {
        await updateUser(u.id, body);
        await load();
      } catch (e) {
        if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "Error");
      }
    },
    [load, onAuthError],
  );

  if (isAdmin === false) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="rounded-card bg-white p-8 text-center shadow-card">
          <h1 className="text-xl font-extrabold text-ink">Acceso restringido</h1>
          <p className="mt-2 text-sm text-ink-muted">
            La gestión de usuarios es solo para administradores de la firma.
          </p>
        </div>
      </div>
    );
  }

  const inputCls =
    "h-10 rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-extrabold text-ink">Usuarios</h1>

      <form onSubmit={submit} className="rounded-card bg-white p-5 shadow-card">
        <h2 className="mb-4 text-sm font-bold text-ink">Nuevo usuario</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="correo@firma.co"
            className={`${inputCls} w-full`}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Contraseña (min. 8)"
            autoComplete="new-password"
            className={`${inputCls} w-full`}
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className={`${inputCls} w-full`}
          >
            <option value="MEMBER">Miembro</option>
            <option value="ADMIN">Administrador</option>
          </select>
          <button
            type="submit"
            disabled={busy}
            className="h-10 rounded-lg bg-primary text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
          >
            {busy ? "Creando…" : "Crear usuario"}
          </button>
        </div>
        {err && <div className="mt-3 text-sm font-medium text-danger">{err}</div>}
      </form>

      <div className="rounded-card bg-white p-2 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3 font-bold">Correo</th>
                <th className="px-4 py-3 font-bold">Rol</th>
                <th className="px-4 py-3 font-bold">Estado</th>
                <th className="px-4 py-3 text-right font-bold">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => {
                const isSelf = u.id === meId;
                return (
                  <tr key={u.id} className="border-b border-line/50 last:border-0">
                    <td className="px-4 py-3 font-semibold text-ink">
                      {u.email}
                      {isSelf && <span className="ml-2 text-xs text-ink-muted">(tú)</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ${
                          u.role === "ADMIN" ? "bg-primary/10 text-primary" : "bg-line text-ink-muted"
                        }`}
                      >
                        {u.role === "ADMIN" ? "Administrador" : "Miembro"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ${
                          u.active ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
                        }`}
                      >
                        {u.active ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!isSelf && (
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              patch(u, { role: u.role === "ADMIN" ? "MEMBER" : "ADMIN" })
                            }
                            className="rounded-lg border border-line px-3 py-1.5 text-xs font-bold text-ink transition hover:border-primary hover:text-primary"
                          >
                            {u.role === "ADMIN" ? "Hacer miembro" : "Hacer admin"}
                          </button>
                          <button
                            type="button"
                            onClick={() => patch(u, { active: !u.active })}
                            className="rounded-lg border border-line px-3 py-1.5 text-xs font-bold text-danger transition hover:bg-danger/5"
                          >
                            {u.active ? "Desactivar" : "Activar"}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin usuarios"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
