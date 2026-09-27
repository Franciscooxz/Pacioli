"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  BarChart3,
  Building2,
  FileText,
  LayoutDashboard,
  LogOut,
  ScrollText,
  X,
} from "lucide-react";
import { clearToken } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, ready: true },
  { href: "/documents", label: "Documentos", icon: FileText, ready: true },
  { href: "/reports", label: "Reportes", icon: BarChart3, ready: true },
  { href: "/rules", label: "Reglas", icon: ScrollText, ready: true },
  { href: "/companies", label: "Empresas", icon: Building2, ready: true },
  { href: "/failures", label: "Fallidos", icon: AlertTriangle, ready: true },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <>
      <nav className="flex flex-1 flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon, ready }) => {
          if (!ready) {
            return (
              <span
                key={href}
                title="Proximamente"
                className="flex cursor-not-allowed items-center gap-3 rounded-card px-3 py-2.5 text-sm font-semibold text-ink-faint"
              >
                <Icon size={20} />
                {label}
                <span className="ml-auto rounded-full bg-line px-2 py-0.5 text-[10px] font-bold text-ink-muted">
                  pronto
                </span>
              </span>
            );
          }
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`flex items-center gap-3 rounded-card px-3 py-2.5 text-sm font-semibold transition ${
                active
                  ? "bg-primary text-white shadow-soft"
                  : "text-ink-muted hover:bg-primary/5 hover:text-primary"
              }`}
            >
              <Icon size={20} />
              {label}
            </Link>
          );
        })}
      </nav>

      <button
        type="button"
        onClick={() => {
          clearToken();
          onNavigate?.();
          router.replace("/login");
        }}
        className="mt-4 flex items-center gap-3 rounded-card px-3 py-2.5 text-sm font-semibold text-ink-muted transition hover:bg-danger/5 hover:text-danger"
      >
        <LogOut size={20} />
        Salir
      </button>
    </>
  );
}

function Logo() {
  return (
    <span className="text-xl font-extrabold text-ink">
      Conta<span className="text-primary">flow</span>
    </span>
  );
}

export default function Sidebar({
  mobileOpen = false,
  onClose,
}: {
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  return (
    <>
      {/* Escritorio: sidebar fijo. */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-white px-4 py-6 md:flex">
        <div className="mb-8 px-2">
          <Logo />
        </div>
        <NavLinks />
      </aside>

      {/* Movil: cajon deslizante sobre un velo. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
          <aside className="relative flex h-full w-64 flex-col border-r border-line bg-white px-4 py-6">
            <div className="mb-8 flex items-center justify-between px-2">
              <Logo />
              <button
                type="button"
                onClick={onClose}
                aria-label="Cerrar menú"
                className="grid h-8 w-8 place-items-center rounded-full text-ink-muted transition hover:bg-canvas"
              >
                <X size={20} />
              </button>
            </div>
            <NavLinks onNavigate={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}
