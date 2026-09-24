"use client";

import { useEffect, useState } from "react";
import { Bell, Search } from "lucide-react";
import { getMe } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function Topbar() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => {
        /* la pantalla ya se protege por token; ignorar aqui */
      });
  }, []);

  const name = me?.email?.split("@")[0] ?? "Usuario";
  const initial = name[0]?.toUpperCase() ?? "U";

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b border-line bg-white px-6">
      <div className="relative hidden max-w-md flex-1 md:block">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
        <input
          placeholder="Buscar..."
          className="h-10 w-full rounded-full border border-line bg-canvas pl-10 pr-4 text-sm outline-none focus:border-primary"
        />
      </div>

      <div className="ml-auto flex items-center gap-4">
        <button
          type="button"
          aria-label="Notificaciones"
          className="relative grid h-10 w-10 place-items-center rounded-full transition hover:bg-canvas"
        >
          <Bell size={20} className="text-ink-muted" />
          <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-danger" />
        </button>

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
