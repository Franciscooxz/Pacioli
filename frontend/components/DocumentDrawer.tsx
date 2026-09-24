"use client";

import { useCallback, useEffect, useState } from "react";
import { Ban, Check, Send, X } from "lucide-react";
import {
  approveDocument,
  getDocument,
  postDocument,
  rejectDocument,
} from "@/lib/api";
import { money, pct } from "@/lib/format";
import type { DocumentDetail } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";

interface Props {
  id: string;
  onClose: () => void;
  onChanged: () => void;
  onAuthError: (e: unknown) => boolean;
}

export default function DocumentDrawer({ id, onClose, onChanged, onAuthError }: Props) {
  const [d, setD] = useState<DocumentDetail | null>(null);
  const [account, setAccount] = useState("");
  const [createRule, setCreateRule] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setD(null);
    setErr("");
    getDocument(id)
      .then((doc) => {
        if (!alive) return;
        setD(doc);
        setAccount(doc.proposed_account_code ?? "");
      })
      .catch((e) => {
        if (!onAuthError(e) && alive) setErr("No se pudo cargar el documento");
      });
    return () => {
      alive = false;
    };
  }, [id, onAuthError]);

  const act = useCallback(
    async (kind: "approve" | "reject" | "post") => {
      if (!d) return;
      setErr("");
      setBusy(true);
      try {
        if (kind === "approve") {
          if (!account.trim()) {
            setErr("Asigna una cuenta contable antes de aprobar");
            setBusy(false);
            return;
          }
          await approveDocument(d.id, account.trim(), createRule);
        } else if (kind === "reject") {
          await rejectDocument(d.id, "rechazado desde la consola");
        } else {
          await postDocument(d.id);
        }
        onChanged();
        onClose();
      } catch (e) {
        if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "Error en la acción");
        setBusy(false);
      }
    },
    [d, account, createRule, onChanged, onClose, onAuthError],
  );

  const c = pct(d?.classification_confidence ?? null);
  const canAct = d?.status === "PENDING_REVIEW" || d?.status === "CLASSIFIED";
  const canPost = d?.status === "CLASSIFIED";

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div
        className="absolute inset-0 bg-ink/30"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="relative flex h-full w-full max-w-lg flex-col bg-canvas shadow-2xl">
        <header className="flex items-center justify-between border-b border-line bg-white px-6 py-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Documento
            </div>
            <div className="text-lg font-extrabold text-ink">
              {d?.document_number ?? (d ? d.id.slice(0, 8) : "Cargando…")}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition hover:bg-canvas"
          >
            <X size={20} />
          </button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto p-6">
          {!d ? (
            <div className="py-16 text-center text-sm text-ink-muted">{err || "Cargando…"}</div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <StatusBadge status={d.status} />
                <span className="text-sm text-ink-muted">{d.doc_type ?? "—"}</span>
              </div>

              <section className="rounded-card bg-white p-5 shadow-card">
                <Field label="Emisor" value={d.issuer_name ?? "—"} />
                <Field label="NIT" value={d.issuer_nit ?? "—"} />
                <Field label="Emisión" value={d.issue_date ?? "—"} />
                <Field label="Moneda" value={d.currency} />
                <Field label="CUFE" value={d.cufe ?? "—"} mono />
              </section>

              <section className="rounded-card bg-white p-5 shadow-card">
                <h3 className="mb-3 text-sm font-bold text-ink">Asiento propuesto</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase text-ink-muted">
                      <th className="pb-2 font-bold">Concepto</th>
                      <th className="pb-2 text-right font-bold">Debe</th>
                      <th className="pb-2 text-right font-bold">Haber</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-line/60">
                      <td className="py-2 text-ink">Base gravable</td>
                      <td className="py-2 text-right text-ink">{money(d.subtotal)}</td>
                      <td className="py-2 text-right text-ink-muted"></td>
                    </tr>
                    {d.taxes.map((t, i) => (
                      <tr key={i} className="border-b border-line/60">
                        <td className="py-2 text-ink">{t.tax_name}</td>
                        <td className="py-2 text-right text-ink">
                          {t.is_withholding ? "" : money(t.tax_amount)}
                        </td>
                        <td className="py-2 text-right text-ink">
                          {t.is_withholding ? money(t.tax_amount) : ""}
                        </td>
                      </tr>
                    ))}
                    <tr className="font-bold">
                      <td className="py-2 text-ink">Total</td>
                      <td className="py-2 text-right"></td>
                      <td className="py-2 text-right text-ink">{money(d.total)}</td>
                    </tr>
                  </tbody>
                </table>
              </section>

              <section className="rounded-card bg-white p-5 shadow-card">
                <h3 className="mb-3 text-sm font-bold text-ink">Clasificación</h3>
                <label htmlFor="acct" className="mb-1.5 block text-xs font-semibold text-ink-muted">
                  Cuenta contable
                </label>
                <input
                  id="acct"
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder="p. ej. 511595"
                  className="h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary"
                />
                <div className="mt-3 flex items-center justify-between text-sm">
                  <span className="text-ink-muted">Confianza de la regla</span>
                  <span
                    className={`font-bold ${
                      c == null ? "text-ink-faint" : c >= 80 ? "text-success" : "text-warning"
                    }`}
                  >
                    {c == null ? "sin regla" : `${c}%`}
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${c ?? 4}%`,
                      background: c == null ? "#cbd5e1" : c >= 80 ? "#00B69B" : "#FCA800",
                    }}
                  />
                </div>
                <label className="mt-4 flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={createRule}
                    onChange={(e) => setCreateRule(e.target.checked)}
                    className="h-4 w-4 rounded border-line text-primary"
                  />
                  Crear regla para este emisor al aprobar
                </label>
              </section>

              {err && (
                <div className="rounded-lg bg-danger/10 px-3 py-2 text-sm font-medium text-danger">
                  {err}
                </div>
              )}
            </>
          )}
        </div>

        {d && (
          <footer className="flex gap-3 border-t border-line bg-white px-6 py-4">
            <button
              type="button"
              disabled={!canAct || busy}
              onClick={() => act("approve")}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-40"
            >
              <Check size={18} /> Aprobar
            </button>
            <button
              type="button"
              disabled={!canPost || busy}
              onClick={() => act("post")}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-success py-2.5 text-sm font-bold text-white transition hover:brightness-95 disabled:opacity-40"
            >
              <Send size={18} /> Contabilizar
            </button>
            <button
              type="button"
              disabled={!canAct || busy}
              onClick={() => act("reject")}
              aria-label="Rechazar"
              className="flex items-center justify-center gap-2 rounded-lg border border-line px-4 py-2.5 text-sm font-bold text-danger transition hover:bg-danger/5 disabled:opacity-40"
            >
              <Ban size={18} />
            </button>
          </footer>
        )}
      </aside>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line/60 py-2 last:border-0">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className={`text-right text-sm font-semibold text-ink ${mono ? "break-all font-mono text-xs" : ""}`}>
        {value}
      </span>
    </div>
  );
}
