"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { getNotificationSummary } from "@/lib/api";
import type { NotificationSummary } from "@/lib/types";
import { useCompany } from "@/components/CompanyProvider";

const POLL_MS = 45_000;

export default function NotificationBell() {
  const { companyId } = useCompany();
  const [sum, setSum] = useState<NotificationSummary | null>(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    getNotificationSummary(companyId)
      .then(setSum)
      .catch(() => {
        /* la pantalla ya se protege por token */
      });
  }, [companyId]);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const total = sum ? sum.pending_review + sum.assigned_to_me + sum.failures : 0;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="Notificaciones"
        onClick={() => setOpen((o) => !o)}
        className="relative grid h-10 w-10 place-items-center rounded-full transition hover:bg-canvas"
      >
        <Bell size={20} className="text-ink-muted" />
        {total > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
            {total > 99 ? "99+" : total}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            role="dialog"
            aria-label="Notificaciones"
            className="absolute right-0 top-12 z-30 w-72 overflow-hidden rounded-card bg-white shadow-card"
          >
            <div className="border-b border-line px-4 py-3 text-sm font-bold text-ink">
              Notificaciones
            </div>
            {total === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-ink-muted">Todo al día</div>
            ) : (
              <ul className="divide-y divide-line/60">
                <Item
                  href="/documents"
                  label="Documentos por revisar"
                  count={sum?.pending_review ?? 0}
                  onClick={() => setOpen(false)}
                />
                <Item
                  href="/documents"
                  label="Asignados a mí"
                  count={sum?.assigned_to_me ?? 0}
                  onClick={() => setOpen(false)}
                />
                <Item
                  href="/failures"
                  label="Fallos de ingesta"
                  count={sum?.failures ?? 0}
                  danger
                  onClick={() => setOpen(false)}
                />
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Item({
  href,
  label,
  count,
  danger,
  onClick,
}: {
  href: string;
  label: string;
  count: number;
  danger?: boolean;
  onClick: () => void;
}) {
  if (count === 0) return null;
  return (
    <li>
      <Link
        href={href}
        onClick={onClick}
        className="flex items-center justify-between px-4 py-3 text-sm transition hover:bg-canvas"
      >
        <span className="text-ink">{label}</span>
        <span
          className={`grid h-6 min-w-[1.5rem] place-items-center rounded-full px-1.5 text-xs font-bold text-white ${
            danger ? "bg-danger" : "bg-primary"
          }`}
        >
          {count}
        </span>
      </Link>
    </li>
  );
}
