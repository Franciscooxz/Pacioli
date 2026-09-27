"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { AuthError, bulkApprove, bulkReject, clearToken, listDocuments } from "@/lib/api";
import { money, pct } from "@/lib/format";
import type { DocStatus, DocumentSummary } from "@/lib/types";
import DocumentDrawer from "@/components/DocumentDrawer";
import StatusBadge from "@/components/StatusBadge";
import { useCompany } from "@/components/CompanyProvider";

type Filter = "review" | "classified" | "all";

const FILTER_STATUS: Record<Filter, DocStatus | undefined> = {
  review: "PENDING_REVIEW",
  classified: "CLASSIFIED",
  all: undefined,
};
const FILTER_LABEL: Record<Filter, string> = {
  review: "En revisión",
  classified: "Clasificados",
  all: "Todos",
};
const DOC_CODE: Record<string, string> = {
  FACTURA_COMPRA: "Compra",
  FACTURA_VENTA: "Venta",
  DOCUMENTO_SOPORTE: "Doc. soporte",
  NOTA_CREDITO: "Nota crédito",
  NOTA_DEBITO: "Nota débito",
  NOMINA_ELECTRONICA: "Nómina",
};

export default function DocumentsPage() {
  const router = useRouter();
  const { companyId } = useCompany();
  const [filter, setFilter] = useState<Filter>("review");
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

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
      setDocs(await listDocuments(FILTER_STATUS[filter], companyId));
      setSelected(new Set());
    } catch (e) {
      onAuthError(e);
    } finally {
      setLoading(false);
    }
  }, [filter, companyId, onAuthError]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter((d) =>
      `${d.issuer_nit ?? ""} ${d.issuer_name ?? ""} ${d.cufe ?? ""}`.toLowerCase().includes(q),
    );
  }, [docs, query]);

  const allSelected = visible.length > 0 && visible.every((d) => selected.has(d.id));

  const toggle = (id: string) => {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const toggleAll = () => {
    setSelected((s) =>
      visible.every((d) => s.has(d.id)) ? new Set() : new Set(visible.map((d) => d.id)),
    );
  };

  const runBulk = useCallback(
    async (action: "approve" | "reject") => {
      const ids = [...selected];
      if (ids.length === 0) return;
      setBusy(true);
      try {
        if (action === "approve") await bulkApprove(ids);
        else await bulkReject(ids);
        await load();
      } catch (e) {
        onAuthError(e);
      } finally {
        setBusy(false);
      }
    },
    [selected, load, onAuthError],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-extrabold text-ink">Documentos</h1>
        <div className="relative w-full max-w-xs">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar NIT / emisor / CUFE"
            className="h-10 w-full rounded-full border border-line bg-white pl-10 pr-4 text-sm outline-none focus:border-primary"
          />
        </div>
      </div>

      <div className="flex gap-2">
        {(["review", "classified", "all"] as Filter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-4 py-2 text-sm font-bold transition ${
              filter === f
                ? "bg-primary text-white shadow-soft"
                : "bg-white text-ink-muted hover:text-primary"
            }`}
          >
            {FILTER_LABEL[f]}
          </button>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-card bg-primary/5 px-4 py-3">
          <span className="text-sm font-bold text-ink">{selected.size} seleccionados</span>
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => runBulk("approve")}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
            >
              Aprobar
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => runBulk("reject")}
              className="rounded-lg border border-line px-4 py-2 text-sm font-bold text-danger transition hover:bg-danger/5 disabled:opacity-50"
            >
              Rechazar
            </button>
          </div>
        </div>
      )}

      <div className="rounded-card bg-white p-2 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Seleccionar todos"
                    className="h-4 w-4 rounded border-line text-primary"
                  />
                </th>
                <th className="px-4 py-3 font-bold">Emisor</th>
                <th className="px-4 py-3 font-bold">NIT</th>
                <th className="px-4 py-3 font-bold">Tipo</th>
                <th className="px-4 py-3 font-bold">Emisión</th>
                <th className="px-4 py-3 text-right font-bold">Total</th>
                <th className="px-4 py-3 text-right font-bold">Conf.</th>
                <th className="px-4 py-3 font-bold">Estado</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((d) => {
                const c = pct(d.classification_confidence);
                return (
                  <tr
                    key={d.id}
                    onClick={() => setOpenId(d.id)}
                    className="cursor-pointer border-b border-line/50 last:border-0 hover:bg-primary/5"
                  >
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(d.id)}
                        onChange={() => toggle(d.id)}
                        aria-label="Seleccionar documento"
                        className="h-4 w-4 rounded border-line text-primary"
                      />
                    </td>
                    <td className="px-4 py-3 font-semibold text-ink">{d.issuer_name ?? "(sin emisor)"}</td>
                    <td className="px-4 py-3 text-ink-muted">{d.issuer_nit ?? "—"}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {d.doc_type ? (DOC_CODE[d.doc_type] ?? d.doc_type) : "—"}
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{d.issue_date ?? "—"}</td>
                    <td className="px-4 py-3 text-right font-semibold text-ink">{money(d.total)}</td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={
                          c == null ? "text-ink-faint" : c >= 80 ? "text-success" : "text-warning"
                        }
                      >
                        {c == null ? "—" : `${c}%`}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={d.status} />
                    </td>
                  </tr>
                );
              })}
              {visible.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-ink-muted">
                    {loading ? "Cargando…" : "Sin documentos"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {openId && (
        <DocumentDrawer
          id={openId}
          onClose={() => setOpenId(null)}
          onChanged={load}
          onAuthError={onAuthError}
        />
      )}
    </div>
  );
}
