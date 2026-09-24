"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  Building2,
  FileText,
  LayoutDashboard,
  LogOut,
  ScrollText,
} from "lucide-react";
import { clearToken } from "@/lib/api";

// `ready: false` = pantalla aun no construida (se habilita en el siguiente incremento).
const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, ready: true },
  { href: "/documents", label: "Documentos", icon: FileText, ready: true },
  { href: "/rules", label: "Reglas", icon: ScrollText, ready: false },
  { href: "/companies", label: "Empresas", icon: Building2, ready: false },
  { href: "/failures", label: "Fallidos", icon: AlertTriangle, ready: false },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-white px-4 py-6 md:flex">
      <div className="mb-8 px-2 text-xl font-extrabold text-ink">
        Conta<span className="text-primary">flow</span>
      </div>

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
          router.replace("/login");
        }}
        className="mt-4 flex items-center gap-3 rounded-card px-3 py-2.5 text-sm font-semibold text-ink-muted transition hover:bg-danger/5 hover:text-danger"
      >
        <LogOut size={20} />
        Salir
      </button>
    </aside>
  );
}
