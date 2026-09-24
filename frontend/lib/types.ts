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
