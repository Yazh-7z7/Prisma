// frontend/src/lib/api.ts
// Typed API client for the Prisma FastAPI backend.

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types (inline for browser-safe import) ────────────────────────────────

export type ValidationStatus =
  | "VALID"
  | "HALLUCINATION_RELATIONSHIP"
  | "HALLUCINATION_DIRECTION"
  | "HALLUCINATION_MAGNITUDE"
  | "HALLUCINATION_VARIABLE"
  | "UNVERIFIED";

export interface DatasetMetadata {
  filename: string;
  rows: number;
  columns: number;
  column_names: string[];
  dtypes: Record<string, string>;
  missing_counts: Record<string, number>;
  missing_total: number;
  numeric_columns: string[];
  categorical_columns: string[];
}

export interface UploadResponse {
  session_id: string;
  metadata: DatasetMetadata;
}

export interface AnalyzeRequest {
  session_id: string;
  model_provider: "ollama" | "openai" | "anthropic";
  model_name?: string;
  use_csvl: boolean;
  num_insights: number;
  openai_key?: string;
  anthropic_key?: string;
}

export interface Claim {
  original_text: string;
  variables: string[];
  relationship: string;
  direction: string;
  strength: string;
  confidence_score: number;
  type: string;
}

export interface ValidationResult {
  claim: Claim;
  extracted_vars: string[];
  status: ValidationStatus;
  reason: string;
  ground_truth?: Record<string, unknown> | null;
}

export interface Metrics {
  total_claims: number;
  valid_claims: number;
  verified_claims: number;
  hallucination_count: number;
  unverified_count: number;
  hallucination_rate: number;
  validity_score: number;
  taxonomy_distribution: Record<string, number>;
  confidence_by_label: Record<string, number>;
  avg_confidence: number;
}

export interface AnalyzeResponse {
  session_id: string;
  status: "complete" | "error";
  metrics: Metrics;
  validation_results: ValidationResult[];
  ground_truth: Record<string, unknown>;
}

// ── API helpers ───────────────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /** POST /upload — upload a CSV/XLSX file */
  upload: async (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
    return handleResponse<UploadResponse>(res);
  },

  /** POST /analyze — run the full pipeline */
  analyze: async (body: AnalyzeRequest): Promise<AnalyzeResponse> => {
    const res = await fetch(`${BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return handleResponse<AnalyzeResponse>(res);
  },

  /** GET /results?session_id=<id> — fetch cached results */
  results: async (session_id: string): Promise<AnalyzeResponse> => {
    const res = await fetch(`${BASE}/results?session_id=${session_id}`);
    return handleResponse<AnalyzeResponse>(res);
  },

  /** GET /health */
  health: async (): Promise<{ status: string; version: string }> => {
    const res = await fetch(`${BASE}/health`);
    return handleResponse(res);
  },
};
