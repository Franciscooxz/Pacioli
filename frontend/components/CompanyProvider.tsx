"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { listCompanies } from "@/lib/api";
import type { Company } from "@/lib/types";

const KEY = "contaflow_company";

interface CompanyCtx {
  companies: Company[];
  companyId: string | null; // null = todas las empresas
  setCompanyId: (id: string | null) => void;
  loading: boolean;
}

const Ctx = createContext<CompanyCtx | null>(null);

export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved) setState(saved);
    } catch {
      /* ignore */
    }
    listCompanies()
      .then(setCompanies)
      .catch(() => {
        /* la pantalla ya se protege por token */
      })
      .finally(() => setLoading(false));
  }, []);

  const setCompanyId = useCallback((id: string | null) => {
    setState(id);
    try {
      if (id) localStorage.setItem(KEY, id);
      else localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ companies, companyId, setCompanyId, loading }),
    [companies, companyId, setCompanyId, loading],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCompany(): CompanyCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCompany debe usarse dentro de CompanyProvider");
  return ctx;
}
