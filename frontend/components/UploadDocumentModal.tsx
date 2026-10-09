"use client";

import { FormEvent, useRef, useState } from "react";
import { UploadCloud, X } from "lucide-react";
import { uploadDocument } from "@/lib/api";
import type { Company } from "@/lib/types";

interface Props {
  companies: Company[];
  defaultCompanyId: string | null;
  onClose: () => void;
  onUploaded: () => void;
  onAuthError: (e: unknown) => boolean;
}

export default function UploadDocumentModal({
  companies,
  defaultCompanyId,
  onClose,
  onUploaded,
  onAuthError,
}: Props) {
  const [companyId, setCompanyId] = useState<string>(
    defaultCompanyId ?? companies[0]?.id ?? "",
  );
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (!companyId) {
      setErr("Elige una empresa.");
      return;
    }
    if (!file) {
      setErr("Elige un archivo XML.");
      return;
    }
    setBusy(true);
    try {
      await uploadDocument(companyId, file);
      setOk(true);
      onUploaded();
    } catch (e) {
      if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "No se pudo subir");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Subir factura"
        className="relative w-full max-w-md rounded-card bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-line px-6 py-4">
          <div className="text-lg font-extrabold text-ink">Subir factura</div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="grid h-9 w-9 place-items-center rounded-full text-ink-muted transition hover:bg-canvas"
          >
            <X size={20} />
          </button>
        </header>

        {ok ? (
          <div className="space-y-4 p-6">
            <p className="text-sm text-ink">
              Factura encolada. En unos segundos aparecerá en la lista tras el parseo y la
              clasificación.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setOk(false);
                  setFile(null);
                  if (inputRef.current) inputRef.current.value = "";
                }}
                className="rounded-lg border border-line px-4 py-2 text-sm font-bold text-ink-muted transition hover:bg-canvas"
              >
                Subir otra
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-primary-hover"
              >
                Cerrar
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4 p-6">
            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-wide text-ink-muted">
                Empresa
              </span>
              <select
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-primary"
              >
                <option value="" disabled>
                  Elige una empresa…
                </option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-xs font-bold uppercase tracking-wide text-ink-muted">
                Archivo XML (UBL 2.1)
              </span>
              <input
                ref={inputRef}
                type="file"
                accept=".xml,application/xml,text/xml"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-ink-muted file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-4 file:py-2 file:text-sm file:font-bold file:text-primary hover:file:bg-primary/20"
              />
            </label>

            {err && <p className="text-sm font-semibold text-danger">{err}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-line px-4 py-2 text-sm font-bold text-ink-muted transition hover:bg-canvas"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
              >
                <UploadCloud size={16} />
                {busy ? "Subiendo…" : "Subir"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
