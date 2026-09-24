"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, FileClock, FileText } from "lucide-react";
import { listDocuments } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";
import AreaChart from "@/components/AreaChart";
import StatCard from "@/components/StatCard";
import StatusBadge from "@/components/StatusBadge";

const fmt = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
const money = (s: string | null) => (s == null ? "—" : `$${fmt.format(Number(s))}`);

export default function DashboardPage() {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then(setDocs)
      .catch(() => {
        /* el layout ya protege por token */
      })
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const by = (s: string) => docs.filter((d) => d.status === s).length;
    return {
      review: by("PENDING_REVIEW"),
      classified: by("CLASSIFIED"),
      posted: by("POSTED"),
      failed: docs.filter((d) => d.status.endsWith("FAILED")).length,
    };
  }, [docs]);

  const series = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of docs) {
      const day = (d.issue_date ?? d.received_at).slice(0, 10);
      map.set(day, (map.get(day) ?? 0) + 1);
    }
    return [...map.keys()]
      .sort()
      .slice(-7)
      .map((day) => ({ label: day.slice(5), value: map.get(day) ?? 0 }));
  }, [docs]);

  const recent = useMemo(
    () => [...docs].sort((a, b) => b.received_at.localeCompare(a.received_at)).slice(0, 6),
    [docs],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-extrabold text-ink">Dashboard</h1>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="En revisión" value={String(stats.review)} icon={FileClock} iconBg="#FFF4DE" iconColor="#FFA756" />
        <StatCard label="Clasificados" value={String(stats.classified)} icon={FileText} iconBg="#E9F0FF" iconColor="#4880FF" />
        <StatCard label="Contabilizados" value={String(stats.posted)} icon={CheckCircle2} iconBg="#DCFCE7" iconColor="#00B69B" />
        <StatCard label="Fallidos" value={String(stats.failed)} icon={AlertTriangle} iconBg="#FFE2E5" iconColor="#EF3826" />
      </div>

      <div className="rounded-card bg-white p-6 shadow-card">
        <h2 className="mb-4 text-lg font-bold text-ink">Documentos por día</h2>
        <AreaChart data={series} />
        {series.length > 0 && (
          <div className="mt-2 flex justify-between px-6 text-xs text-ink-muted">
            {series.map((s, i) => (
              <span key={i}>{s.label}</span>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-card bg-white p-6 shadow-card">
        <h2 className="mb-4 text-lg font-bold text-ink">Documentos recientes</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="pb-3 font-bold">Emisor</th>
                <th className="pb-3 font-bold">NIT</th>
                <th className="pb-3 font-bold">Fecha</th>
                <th className="pb-3 text-right font-bold">Total</th>
                <th className="pb-3 font-bold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((d) => (
                <tr key={d.id} className="border-b border-line/60 last:border-0">
                  <td className="py-3 font-semibold text-ink">{d.issuer_name ?? "—"}</td>
                  <td className="py-3 text-ink-muted">{d.issuer_nit ?? "—"}</td>
                  <td className="py-3 text-ink-muted">{d.issue_date ?? "—"}</td>
                  <td className="py-3 text-right font-semibold text-ink">{money(d.total)}</td>
                  <td className="py-3">
                    <StatusBadge status={d.status} />
                  </td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin documentos"}
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
