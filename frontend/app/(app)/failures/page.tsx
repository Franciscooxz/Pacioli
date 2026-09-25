"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthError, clearToken, listFailures, resolveFailure } from "@/lib/api";
import type { IngestionFailure } from "@/lib/types";

type Filter = "pending" | "all";

const STAGE_LABEL: Record<string, string> = {
  MAIL_EXTRACTION: "Correo",
  INGEST: "Ingesta",
  PARSE: "Parseo",
  CLASSIFY: "Clasificación",
  LLM_SUGGEST: "LLM",
  POST: "Posteo",
};

export default function FailuresPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("pending");
  const [rows, setRows] = useState<IngestionFailure[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

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
      setRows(await listFailures(filter === "pending" ? false : undefined));
    } catch (e) {
      onAuthError(e);
    } finally {
      setLoading(false);
    }
  }, [filter, onAuthError]);

  useEffect(() => {
    void load();
  }, [load]);

  const resolve = useCallback(
    async (id: string) => {
      setBusyId(id);
      try {
        await resolveFailure(id);
        await load();
      } catch (e) {
        onAuthError(e);
      } finally {
        setBusyId(null);
      }
    },
    [load, onAuthError],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-extrabold text-ink">Fallidos</h1>

      <div className="flex gap-2">
        {(["pending", "all"] as Filter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-4 py-2 text-sm font-bold transition ${
              filter === f ? "bg-primary text-white shadow-soft" : "bg-white text-ink-muted hover:text-primary"
            }`}
          >
            {f === "pending" ? "Pendientes" : "Todos"}
          </button>
        ))}
      </div>

      <div className="rounded-card bg-white p-2 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3 font-bold">Fecha</th>
                <th className="px-4 py-3 font-bold">Etapa</th>
                <th className="px-4 py-3 font-bold">Motivo</th>
                <th className="px-4 py-3 font-bold">Ref</th>
                <th className="px-4 py-3 font-bold">Estado</th>
                <th className="px-4 py-3 text-right font-bold">Acción</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.id} className="border-b border-line/50 last:border-0">
                  <td className="px-4 py-3 text-ink-muted">{f.created_at.slice(0, 16).replace("T", " ")}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                      {STAGE_LABEL[f.stage] ?? f.stage}
                    </span>
                  </td>
                  <td className="max-w-md px-4 py-3 text-ink">
                    <span className="line-clamp-2">{f.reason}</span>
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{f.source_ref ?? "—"}</td>
                  <td className="px-4 py-3">
                    {f.resolved_at ? (
                      <span className="inline-flex rounded-full bg-success/10 px-3 py-1 text-xs font-bold text-success">
                        Resuelto
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-danger/10 px-3 py-1 text-xs font-bold text-danger">
                        Pendiente
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!f.resolved_at && (
                      <button
                        type="button"
                        disabled={busyId === f.id}
                        onClick={() => resolve(f.id)}
                        className="rounded-lg border border-line px-3 py-1.5 text-xs font-bold text-ink transition hover:border-primary hover:text-primary disabled:opacity-40"
                      >
                        Marcar atendido
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin fallos"}
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
