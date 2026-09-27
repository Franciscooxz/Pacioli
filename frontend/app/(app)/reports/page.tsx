"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Download } from "lucide-react";
import { AuthError, clearToken, downloadReportCsv, getReportSummary } from "@/lib/api";
import { money } from "@/lib/format";
import { useCompany } from "@/components/CompanyProvider";
import type { DocStatus, ReportSummary } from "@/lib/types";

const STATUSES: { value: DocStatus | ""; label: string }[] = [
  { value: "", label: "Todos los estados" },
  { value: "POSTED", label: "Contabilizados" },
  { value: "PENDING_REVIEW", label: "En revisión" },
  { value: "CLASSIFIED", label: "Clasificados" },
  { value: "REJECTED", label: "Rechazados" },
];

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card bg-white p-5 shadow-card">
      <div className="text-sm font-semibold text-ink-muted">{label}</div>
      <div className="mt-2 text-2xl font-extrabold text-ink">{value}</div>
    </div>
  );
}

export default function ReportsPage() {
  const router = useRouter();
  const { companyId } = useCompany();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [status, setStatus] = useState<DocStatus | "">("");
  const [data, setData] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

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
    setErr("");
    try {
      setData(
        await getReportSummary({
          companyId,
          status: status || undefined,
          from: from || undefined,
          to: to || undefined,
        }),
      );
    } catch (e) {
      if (!onAuthError(e)) setErr("No se pudo cargar el reporte");
    } finally {
      setLoading(false);
    }
  }, [companyId, status, from, to, onAuthError]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportCsv = useCallback(async () => {
    setBusy(true);
    try {
      await downloadReportCsv({
        companyId,
        status: status || undefined,
        from: from || undefined,
        to: to || undefined,
      });
    } catch (e) {
      if (!onAuthError(e)) setErr("No se pudo exportar");
    } finally {
      setBusy(false);
    }
  }, [companyId, status, from, to, onAuthError]);

  const inputCls =
    "h-10 rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-primary";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-extrabold text-ink">Reportes</h1>
        <button
          type="button"
          onClick={exportCsv}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
        >
          <Download size={18} /> {busy ? "Exportando…" : "Exportar CSV"}
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-card bg-white p-4 shadow-card">
        <div>
          <label className="mb-1 block text-xs font-semibold text-ink-muted">Desde</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold text-ink-muted">Hasta</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold text-ink-muted">Estado</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as DocStatus | "")}
            className={inputCls}
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {err && (
        <div className="rounded-lg bg-danger/10 px-3 py-2 text-sm font-medium text-danger">{err}</div>
      )}

      <div className="grid grid-cols-2 gap-5 lg:grid-cols-5">
        <Card label="Documentos" value={data ? String(data.count) : "—"} />
        <Card label="Base gravable" value={data ? money(data.subtotal) : "—"} />
        <Card label="IVA" value={data ? money(data.total_tax) : "—"} />
        <Card label="Retenciones" value={data ? money(data.total_withholding) : "—"} />
        <Card label="Total" value={data ? money(data.total) : "—"} />
      </div>

      <div className="rounded-card bg-white p-6 shadow-card">
        <h2 className="mb-4 text-lg font-bold text-ink">Por mes</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-3 font-bold">Mes</th>
                <th className="py-3 text-right font-bold">Documentos</th>
                <th className="py-3 text-right font-bold">Total</th>
              </tr>
            </thead>
            <tbody>
              {(data?.by_month ?? []).map((b) => (
                <tr key={b.month} className="border-b border-line/60 last:border-0">
                  <td className="py-3 font-semibold text-ink">{b.month}</td>
                  <td className="py-3 text-right text-ink-muted">{b.count}</td>
                  <td className="py-3 text-right font-semibold text-ink">{money(b.total)}</td>
                </tr>
              ))}
              {(!data || data.by_month.length === 0) && (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin datos en el rango"}
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
