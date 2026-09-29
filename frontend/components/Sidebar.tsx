"use client";

import { useEffect, useState } from "react";
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
  Users,
  X,
} from "lucide-react";
import { clearToken, getMe } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
  { href: "/documents", label: "Documentos", icon: FileText, adminOnly: false },
  { href: "/reports", label: "Reportes", icon: BarChart3, adminOnly: false },
  { href: "/rules", label: "Reglas", icon: ScrollText, adminOnly: false },
  { href: "/companies", label: "Empresas", icon: Building2, adminOnly: false },
  { href: "/failures", label: "Fallidos", icon: AlertTriangle, adminOnly: false },
  { href: "/users", label: "Usuarios", icon: Users, adminOnly: true },
];

function NavLinks({ onNavigate, isAdmin }: { onNavigate?: () => void; isAdmin: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <>
      <nav className="flex flex-1 flex-col gap-1">
        {NAV.filter((n) => !n.adminOnly || isAdmin).map(({ href, label, icon: Icon }) => {
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
      Drax<span className="text-primary">ia</span>
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
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    getMe()
      .then((m) => setIsAdmin(m.role === "ADMIN"))
      .catch(() => {
        /* el layout ya protege por token */
      });
  }, []);

  return (
    <>
      {/* Escritorio: sidebar fijo. */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-white px-4 py-6 md:flex">
        <div className="mb-8 px-2">
          <Logo />
        </div>
        <NavLinks isAdmin={isAdmin} />
      </aside>

      {/* Movil: cajon deslizante sobre un velo. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Menú de navegación"
            className="relative flex h-full w-64 flex-col border-r border-line bg-white px-4 py-6"
          >
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
            <NavLinks onNavigate={onClose} isAdmin={isAdmin} />
          </aside>
        </div>
      )}
    </>
  );
}
