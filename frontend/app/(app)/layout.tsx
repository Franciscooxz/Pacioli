"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";
import { CompanyProvider } from "@/components/CompanyProvider";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) return null;

  return (
    <CompanyProvider>
      <div className="flex min-h-screen bg-canvas">
        <Sidebar mobileOpen={menuOpen} onClose={() => setMenuOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onMenu={() => setMenuOpen(true)} />
          <main className="flex-1 p-4 md:p-6">{children}</main>
        </div>
      </div>
    </CompanyProvider>
  );
}
