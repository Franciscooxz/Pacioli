"use client";

import { useEffect, useState } from "react";
import { Building2, Menu } from "lucide-react";
import { getMe } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useCompany } from "@/components/CompanyProvider";
import NotificationBell from "@/components/NotificationBell";

export default function Topbar({ onMenu }: { onMenu?: () => void }) {
  const [me, setMe] = useState<Me | null>(null);
  const { companies, companyId, setCompanyId } = useCompany();

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => {
        /* la pantalla ya se protege por token */
      });
  }, []);

  const name = me?.email?.split("@")[0] ?? "Usuario";
  const initial = name[0]?.toUpperCase() ?? "U";

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b border-line bg-white px-4 md:px-6">
      <button
        type="button"
        onClick={onMenu}
        aria-label="Abrir menú"
        className="grid h-10 w-10 place-items-center rounded-full text-ink-muted transition hover:bg-canvas md:hidden"
      >
        <Menu size={22} />
      </button>

      <div className="flex items-center gap-2">
        <Building2 size={18} className="text-ink-muted" />
        <select
          value={companyId ?? ""}
          onChange={(e) => setCompanyId(e.target.value || null)}
          aria-label="Empresa activa"
          className="h-10 max-w-[220px] rounded-lg border border-line bg-canvas px-2 text-sm font-semibold text-ink outline-none focus:border-primary"
        >
          <option value="">Todas las empresas</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <NotificationBell />

        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-full bg-primary text-sm font-bold text-white">
            {initial}
          </div>
          <div className="hidden leading-tight sm:block">
            <div className="text-sm font-bold text-ink">{name}</div>
            <div className="text-xs text-ink-muted">{me?.role ?? ""}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
