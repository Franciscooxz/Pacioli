export interface Me {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
}

export type DocStatus =
  | "RECEIVED"
  | "PARSED"
  | "CLASSIFIED"
  | "PENDING_REVIEW"
  | "POSTED"
  | "PARSE_FAILED"
  | "POSTING_FAILED"
  | "REJECTED";

export interface DocumentSummary {
  id: string;
  status: DocStatus;
  doc_type: string | null;
  cufe: string | null;
  document_number: string | null;
  issuer_nit: string | null;
  issuer_name: string | null;
  total: string | null;
  issue_date: string | null;
  received_at: string;
  proposed_account_code: string | null;
  classification_confidence: string | null;
}

export interface LineOut {
  line_id: string;
  description: string | null;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface TaxOut {
  category: string;
  is_withholding: boolean;
  tax_name: string;
  percent: string;
  taxable_amount: string;
  tax_amount: string;
  municipality: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  receiver_nit: string | null;
  currency: string;
  subtotal: string | null;
  total_tax: string | null;
  total_withholding: string | null;
  proposed_cost_center: string | null;
  lines: LineOut[];
  taxes: TaxOut[];
}

export interface Company {
  id: string;
  name: string;
  nit: string;
  active: boolean;
  has_odoo: boolean;
  has_imap: boolean;
}

export interface CompanyDetail {
  id: string;
  name: string;
  nit: string;
  active: boolean;
  odoo_url: string | null;
  odoo_db: string | null;
  odoo_username: string | null;
  imap_host: string | null;
  imap_port: number | null;
  imap_username: string | null;
  posting_config: Record<string, unknown> | null;
  has_odoo_password: boolean;
  has_imap_password: boolean;
}

export interface CompanyInput {
  name: string;
  nit: string;
  active?: boolean;
  odoo_url?: string | null;
  odoo_db?: string | null;
  odoo_username?: string | null;
  odoo_password?: string | null;
  imap_host?: string | null;
  imap_port?: number | null;
  imap_username?: string | null;
  imap_password?: string | null;
  posting_config?: Record<string, string> | null;
}

export interface Rule {
  id: string;
  company_id: string;
  account_code: string;
  issuer_nit: string | null;
  match_pattern: string | null;
  cost_center: string | null;
  priority: number;
  confidence: string;
  active: boolean;
}

export interface IngestionFailure {
  id: string;
  stage: string;
  company_id: string | null;
  document_id: string | null;
  task_name: string | null;
  source_ref: string | null;
  reason: string;
  raw_uri: string | null;
  resolved_at: string | null;
  created_at: string;
}
