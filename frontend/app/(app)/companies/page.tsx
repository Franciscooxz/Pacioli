"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { AuthError, clearToken } from "@/lib/api";
import { useCompany } from "@/components/CompanyProvider";
import CompanyDrawer from "@/components/CompanyDrawer";

function Pill({ on, onText, offText }: { on: boolean; onText: string; offText: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-bold ${
        on ? "bg-success/10 text-success" : "bg-line text-ink-muted"
      }`}
    >
      {on ? onText : offText}
    </span>
  );
}

export default function CompaniesPage() {
  const router = useRouter();
  const { companies, loading, refresh } = useCompany();
  // undefined = cerrado · null = crear · string = editar
  const [openId, setOpenId] = useState<string | null | undefined>(undefined);

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

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-ink">Empresas</h1>
        <button
          type="button"
          onClick={() => setOpenId(null)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover"
        >
          <Plus size={18} /> Nueva empresa
        </button>
      </div>

      <div className="rounded-card bg-white p-2 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3 font-bold">Nombre</th>
                <th className="px-4 py-3 font-bold">NIT</th>
                <th className="px-4 py-3 font-bold">Estado</th>
                <th className="px-4 py-3 font-bold">Odoo</th>
                <th className="px-4 py-3 font-bold">Buzón IMAP</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setOpenId(c.id)}
                  className="cursor-pointer border-b border-line/50 last:border-0 hover:bg-primary/5"
                >
                  <td className="px-4 py-3 font-semibold text-ink">{c.name}</td>
                  <td className="px-4 py-3 text-ink-muted">{c.nit}</td>
                  <td className="px-4 py-3">
                    <Pill on={c.active} onText="Activa" offText="Inactiva" />
                  </td>
                  <td className="px-4 py-3">
                    <Pill on={c.has_odoo} onText="Configurado" offText="Sin Odoo" />
                  </td>
                  <td className="px-4 py-3">
                    <Pill on={c.has_imap} onText="Configurado" offText="Sin buzón" />
                  </td>
                </tr>
              ))}
              {companies.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin empresas — crea la primera"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {openId !== undefined && (
        <CompanyDrawer
          id={openId}
          onClose={() => setOpenId(undefined)}
          onSaved={refresh}
          onAuthError={onAuthError}
        />
      )}
    </div>
  );
}
