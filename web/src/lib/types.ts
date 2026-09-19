export type Status = "exact" | "ai" | "missing" | "portal_only" | "unmatched";

export interface MatchRow {
  register_no: string;
  portal_no: string;
  supplier_name: string;
  supplier_gstin: string;
  tax: number;
  status: Status;
  ai_conf: number;
  similarity: number;
  reason: string;
  engine: string;
  phone: string;
  email: string;
  message: string;
}

export interface ExcelRow {
  register_no: string;
  supplier_name: string;
  tax: number;
  portal_no: string;
}

export interface Snapshot {
  generated_at: string;
  period: string;
  fp: string;
  recipient_gstin: string;
  totals: {
    total: number;
    exact: number;
    rescued: number;
    risk: number;
    write_off: number;
  };
  counts: {
    books: number;
    portal: number;
    excel_unmatched: number;
    rescued: number;
    missing: number;
    portal_only: number;
  };
  excel_unmatched: ExcelRow[];
  matches: MatchRow[];
  cost: {
    engines: Record<string, number>;
    tokens_in: number;
    tokens_out: number;
    usd: number;
  };
}

export interface ActivityEvent {
  at: string;
  tag: "EXCEL" | "AGENT" | "A2A" | "DATA";
  text: string;
}

export interface DispatchResult {
  ok: boolean;
  mode: string;
  detail: string;
  messageId: string | null;
}
