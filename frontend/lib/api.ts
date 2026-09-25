import type {
  Company,
  DocStatus,
  DocumentDetail,
  DocumentSummary,
  IngestionFailure,
  Me,
  Rule,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "contaflow_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}
export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export class AuthError extends Error {}

async function authed<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new AuthError("sin sesion");
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) {
    clearToken();
    throw new AuthError("sesion expirada");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Error ${res.status}`);
  }
  if (res.status === 202 || res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? "Credenciales invalidas");
  }
  const data = (await res.json()) as { access_token: string };
  setToken(data.access_token);
}

export function getMe(): Promise<Me> {
  return authed<Me>("/auth/me");
}

export function listDocuments(
  status?: DocStatus,
  companyId?: string | null,
): Promise<DocumentSummary[]> {
  const p = new URLSearchParams();
  if (status) p.set("status", status);
  if (companyId) p.set("company_id", companyId);
  const q = p.toString();
  return authed<DocumentSummary[]>(`/documents${q ? `?${q}` : ""}`);
}

export function getDocument(id: string): Promise<DocumentDetail> {
  return authed<DocumentDetail>(`/documents/${id}`);
}

export function approveDocument(
  id: string,
  accountCode: string,
  createRule = false,
): Promise<DocumentSummary> {
  return authed<DocumentSummary>(`/documents/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ account_code: accountCode, create_rule: createRule }),
  });
}

export function rejectDocument(id: string, reason?: string): Promise<DocumentSummary> {
  return authed<DocumentSummary>(`/documents/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
  });
}

export function postDocument(id: string): Promise<void> {
  return authed<void>(`/documents/${id}/post`, { method: "POST" });
}

export function listCompanies(): Promise<Company[]> {
  return authed<Company[]>("/companies");
}

export function listRules(companyId?: string): Promise<Rule[]> {
  const q = companyId ? `?company_id=${companyId}` : "";
  return authed<Rule[]>(`/rules${q}`);
}

export interface RuleInput {
  company_id: string;
  account_code: string;
  issuer_nit?: string | null;
  match_pattern?: string | null;
  priority?: number;
  confidence?: string;
}

export function createRule(body: RuleInput): Promise<Rule> {
  return authed<Rule>("/rules", { method: "POST", body: JSON.stringify(body) });
}

export function updateRule(
  id: string,
  body: Partial<{ active: boolean; account_code: string; priority: number }>,
): Promise<Rule> {
  return authed<Rule>(`/rules/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function listFailures(
  resolved?: boolean,
  companyId?: string | null,
): Promise<IngestionFailure[]> {
  const p = new URLSearchParams();
  if (resolved !== undefined) p.set("resolved", String(resolved));
  if (companyId) p.set("company_id", companyId);
  const q = p.toString();
  return authed<IngestionFailure[]>(`/failures${q ? `?${q}` : ""}`);
}

export function resolveFailure(id: string): Promise<IngestionFailure> {
  return authed<IngestionFailure>(`/failures/${id}/resolve`, { method: "POST" });
}
