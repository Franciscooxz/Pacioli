"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AuthError,
  clearToken,
  createRule,
  listCompanies,
  listRules,
  updateRule,
} from "@/lib/api";
import type { Company, Rule } from "@/lib/types";

export default function RulesPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const [companyId, setCompanyId] = useState("");
  const [issuerNit, setIssuerNit] = useState("");
  const [account, setAccount] = useState("");
  const [priority, setPriority] = useState("100");

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
      const [cs, rs] = await Promise.all([listCompanies(), listRules()]);
      setCompanies(cs);
      setRules(rs);
    } catch (e) {
      onAuthError(e);
    } finally {
      setLoading(false);
    }
  }, [onAuthError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (companies.length > 0 && !companyId) setCompanyId(companies[0].id);
  }, [companies, companyId]);

  const nameById = useMemo(
    () => new Map(companies.map((c) => [c.id, c.name])),
    [companies],
  );

  const submit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setErr("");
      if (!companyId || !account.trim()) {
        setErr("Empresa y cuenta contable son obligatorias");
        return;
      }
      setBusy(true);
      try {
        await createRule({
          company_id: companyId,
          account_code: account.trim(),
          issuer_nit: issuerNit.trim() || null,
          priority: Number(priority) || 100,
        });
        setAccount("");
        setIssuerNit("");
        await load();
      } catch (e) {
        if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "Error al crear la regla");
      } finally {
        setBusy(false);
      }
    },
    [companyId, account, issuerNit, priority, load, onAuthError],
  );

  const toggle = useCallback(
    async (r: Rule) => {
      try {
        await updateRule(r.id, { active: !r.active });
        await load();
      } catch (e) {
        onAuthError(e);
      }
    },
    [load, onAuthError],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-extrabold text-ink">Reglas de clasificación</h1>

      <form onSubmit={submit} className="rounded-card bg-white p-5 shadow-card">
        <h2 className="mb-4 text-sm font-bold text-ink">Nueva regla</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Labeled label="Empresa">
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
            >
              {companies.length === 0 && <option value="">Sin empresas</option>}
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Labeled>
          <Labeled label="NIT emisor (opcional)">
            <input
              value={issuerNit}
              onChange={(e) => setIssuerNit(e.target.value)}
              placeholder="900123456"
              className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
            />
          </Labeled>
          <Labeled label="Cuenta contable">
            <input
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              placeholder="511595"
              className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
            />
          </Labeled>
          <Labeled label="Prioridad">
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
            />
          </Labeled>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={busy}
              className="h-10 w-full rounded-lg bg-primary text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
            >
              {busy ? "Creando…" : "Crear regla"}
            </button>
          </div>
        </div>
        {err && <div className="mt-3 text-sm font-medium text-danger">{err}</div>}
      </form>

      <div className="rounded-card bg-white p-2 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3 font-bold">Empresa</th>
                <th className="px-4 py-3 font-bold">NIT emisor</th>
                <th className="px-4 py-3 font-bold">Patrón</th>
                <th className="px-4 py-3 font-bold">Cuenta</th>
                <th className="px-4 py-3 text-right font-bold">Prioridad</th>
                <th className="px-4 py-3 text-right font-bold">Confianza</th>
                <th className="px-4 py-3 font-bold">Activa</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-line/50 last:border-0">
                  <td className="px-4 py-3 font-semibold text-ink">
                    {nameById.get(r.company_id) ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{r.issuer_nit ?? "—"}</td>
                  <td className="px-4 py-3 text-ink-muted">{r.match_pattern ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-ink">{r.account_code}</td>
                  <td className="px-4 py-3 text-right text-ink-muted">{r.priority}</td>
                  <td className="px-4 py-3 text-right text-ink-muted">
                    {Math.round(Number(r.confidence) * 100)}%
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggle(r)}
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-bold transition ${
                        r.active
                          ? "bg-success/10 text-success hover:bg-success/20"
                          : "bg-line text-ink-muted hover:bg-line/70"
                      }`}
                    >
                      {r.active ? "Activa" : "Inactiva"}
                    </button>
                  </td>
                </tr>
              ))}
              {rules.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin reglas"}
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

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-semibold text-ink-muted">{label}</label>
      {children}
    </div>
  );
}
