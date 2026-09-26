"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import { createCompany, getCompany, updateCompany } from "@/lib/api";
import type { CompanyInput } from "@/lib/types";

interface Props {
  id: string | null; // null = crear
  onClose: () => void;
  onSaved: () => void;
  onAuthError: (e: unknown) => boolean;
}

const POSTING_FIELDS: { key: string; label: string }[] = [
  { key: "payable_account_code", label: "CxP proveedor" },
  { key: "iva_account_code", label: "IVA descontable" },
  { key: "retefuente_account_code", label: "Retefuente x pagar" },
  { key: "reteiva_account_code", label: "ReteIVA x pagar" },
  { key: "reteica_account_code", label: "ReteICA x pagar" },
  { key: "receivable_account_code", label: "CxC cliente" },
  { key: "iva_generado_account_code", label: "IVA generado" },
  { key: "retefuente_favor_account_code", label: "Retefuente a favor" },
  { key: "reteiva_favor_account_code", label: "ReteIVA a favor" },
  { key: "reteica_favor_account_code", label: "ReteICA a favor" },
];

const EMPTY = {
  name: "",
  nit: "",
  odoo_url: "",
  odoo_db: "",
  odoo_username: "",
  odoo_password: "",
  imap_host: "",
  imap_port: "",
  imap_username: "",
  imap_password: "",
};

export default function CompanyDrawer({ id, onClose, onSaved, onAuthError }: Props) {
  const [form, setForm] = useState({ ...EMPTY });
  const [active, setActive] = useState(true);
  const [posting, setPosting] = useState<Record<string, string>>({});
  const [hasOdooPass, setHasOdooPass] = useState(false);
  const [hasImapPass, setHasImapPass] = useState(false);
  const [loaded, setLoaded] = useState(id === null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (id === null) return;
    let alive = true;
    getCompany(id)
      .then((c) => {
        if (!alive) return;
        setForm({
          name: c.name,
          nit: c.nit,
          odoo_url: c.odoo_url ?? "",
          odoo_db: c.odoo_db ?? "",
          odoo_username: c.odoo_username ?? "",
          odoo_password: "",
          imap_host: c.imap_host ?? "",
          imap_port: c.imap_port != null ? String(c.imap_port) : "",
          imap_username: c.imap_username ?? "",
          imap_password: "",
        });
        setActive(c.active);
        setHasOdooPass(c.has_odoo_password);
        setHasImapPass(c.has_imap_password);
        const pc: Record<string, string> = {};
        for (const [k, v] of Object.entries(c.posting_config ?? {})) pc[k] = v == null ? "" : String(v);
        setPosting(pc);
        setLoaded(true);
      })
      .catch((e) => {
        if (!onAuthError(e) && alive) setErr("No se pudo cargar la empresa");
      });
    return () => {
      alive = false;
    };
  }, [id, onAuthError]);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setErr("");
      if (!form.name.trim() || !form.nit.trim()) {
        setErr("Nombre y NIT son obligatorios");
        return;
      }
      const posting_config = Object.fromEntries(
        Object.entries(posting).filter(([, v]) => v.trim()),
      ) as Record<string, string>;
      const body: CompanyInput = {
        name: form.name.trim(),
        nit: form.nit.trim(),
        active,
        odoo_url: form.odoo_url.trim() || null,
        odoo_db: form.odoo_db.trim() || null,
        odoo_username: form.odoo_username.trim() || null,
        imap_host: form.imap_host.trim() || null,
        imap_port: form.imap_port.trim() ? Number(form.imap_port) : null,
        imap_username: form.imap_username.trim() || null,
        posting_config,
      };
      // Las contrasenas solo se envian si el usuario escribio una nueva.
      if (form.odoo_password) body.odoo_password = form.odoo_password;
      if (form.imap_password) body.imap_password = form.imap_password;

      setBusy(true);
      try {
        if (id === null) await createCompany(body);
        else await updateCompany(id, body);
        onSaved();
        onClose();
      } catch (e) {
        if (!onAuthError(e)) setErr(e instanceof Error ? e.message : "Error al guardar");
        setBusy(false);
      }
    },
    [form, active, posting, id, onSaved, onClose, onAuthError],
  );

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden="true" />
      <aside className="relative flex h-full w-full max-w-xl flex-col bg-canvas shadow-2xl">
        <header className="flex items-center justify-between border-b border-line bg-white px-6 py-4">
          <div className="text-lg font-extrabold text-ink">
            {id === null ? "Nueva empresa" : "Editar empresa"}
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

        {!loaded ? (
          <div className="py-16 text-center text-sm text-ink-muted">{err || "Cargando…"}</div>
        ) : (
          <form onSubmit={save} className="flex flex-1 flex-col overflow-hidden">
            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              <Section title="Datos">
                <Field label="Nombre">
                  <input value={form.name} onChange={set("name")} className={inputCls} />
                </Field>
                <Field label="NIT">
                  <input value={form.nit} onChange={set("nit")} className={inputCls} />
                </Field>
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={(e) => setActive(e.target.checked)}
                    className="h-4 w-4 rounded border-line text-primary"
                  />
                  Empresa activa
                </label>
              </Section>

              <Section title="Odoo">
                <Field label="URL">
                  <input value={form.odoo_url} onChange={set("odoo_url")} placeholder="https://odoo.ejemplo.com" className={inputCls} />
                </Field>
                <Field label="Base de datos">
                  <input value={form.odoo_db} onChange={set("odoo_db")} className={inputCls} />
                </Field>
                <Field label="Usuario">
                  <input value={form.odoo_username} onChange={set("odoo_username")} className={inputCls} />
                </Field>
                <Field label="Contraseña / API key">
                  <input
                    type="password"
                    value={form.odoo_password}
                    onChange={set("odoo_password")}
                    placeholder={hasOdooPass ? "•••••• (sin cambios)" : "—"}
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
              </Section>

              <Section title="Buzón IMAP">
                <Field label="Host">
                  <input value={form.imap_host} onChange={set("imap_host")} placeholder="imap.ejemplo.com" className={inputCls} />
                </Field>
                <Field label="Puerto">
                  <input value={form.imap_port} onChange={set("imap_port")} placeholder="993" className={inputCls} />
                </Field>
                <Field label="Usuario">
                  <input value={form.imap_username} onChange={set("imap_username")} className={inputCls} />
                </Field>
                <Field label="Contraseña">
                  <input
                    type="password"
                    value={form.imap_password}
                    onChange={set("imap_password")}
                    placeholder={hasImapPass ? "•••••• (sin cambios)" : "—"}
                    autoComplete="new-password"
                    className={inputCls}
                  />
                </Field>
              </Section>

              <Section title="Cuentas contables (posting a Odoo)">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {POSTING_FIELDS.map(({ key, label }) => (
                    <div key={key}>
                      <label className="mb-1 block text-xs font-semibold text-ink-muted">{label}</label>
                      <input
                        value={posting[key] ?? ""}
                        onChange={(e) => setPosting((p) => ({ ...p, [key]: e.target.value }))}
                        placeholder="código"
                        className={inputCls}
                      />
                    </div>
                  ))}
                </div>
              </Section>

              {err && (
                <div className="rounded-lg bg-danger/10 px-3 py-2 text-sm font-medium text-danger">
                  {err}
                </div>
              )}
            </div>

            <footer className="flex justify-end gap-3 border-t border-line bg-white px-6 py-4">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-line px-4 py-2.5 text-sm font-bold text-ink-muted transition hover:bg-canvas"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={busy}
                className="rounded-lg bg-primary px-6 py-2.5 text-sm font-bold text-white transition hover:bg-primary-hover disabled:opacity-50"
              >
                {busy ? "Guardando…" : "Guardar"}
              </button>
            </footer>
          </form>
        )}
      </aside>
    </div>
  );
}

const inputCls =
  "h-10 w-full rounded-lg border border-line bg-canvas px-3 text-sm outline-none focus:border-primary";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-card bg-white p-5 shadow-card">
      <h3 className="mb-4 text-sm font-bold text-ink">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold text-ink-muted">{label}</label>
      {children}
    </div>
  );
}
