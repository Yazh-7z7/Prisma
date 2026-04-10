// shared/types.ts — Shared TypeScript type definitions
// Mirror of shared/types.py for the Next.js frontend.

// ── Hallucination taxonomy ────────────────────────────────────────────────────

export type ValidationStatus =
  | "VALID"
  | "HALLUCINATION_RELATIONSHIP"
  | "HALLUCINATION_DIRECTION"
  | "HALLUCINATION_MAGNITUDE"
  | "HALLUCINATION_VARIABLE"
  | "UNVERIFIED";

export const TAXONOMY_LABELS: ValidationStatus[] = [
  "VALID",
  "HALLUCINATION_RELATIONSHIP",
  "HALLUCINATION_DIRECTION",
  "HALLUCINATION_MAGNITUDE",
  "HALLUCINATION_VARIABLE",
  "UNVERIFIED",
];

// ── Status badge colour map ───────────────────────────────────────────────────

export const STATUS_COLORS: Record<ValidationStatus, string> = {
  VALID: "#22c55e",                    // green-500
  HALLUCINATION_RELATIONSHIP: "#ef4444", // red-500
  HALLUCINATION_DIRECTION: "#f97316",   // orange-500
  HALLUCINATION_MAGNITUDE: "#eab308",   // yellow-500
  HALLUCINATION_VARIABLE: "#a855f7",    // purple-500
  UNVERIFIED: "#6b7280",               // gray-500
};

// ── Claim ─────────────────────────────────────────────────────────────────────

export interface Claim {
  original_text: string;
  variables: string[];
  relationship: string;
  direction: "positive" | "negative" | "unknown";
  strength: "strong" | "moderate" | "weak" | "unknown";
  confidence_score: number;
  type: string;
}

// ── ValidationResult ──────────────────────────────────────────────────────────

export interface ValidationResult {
  claim: Claim;
  extracted_vars: string[];
  status: ValidationStatus;
  reason: string;
  ground_truth?: Record<string, unknown> | null;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface Metrics {
  total_claims: number;
  valid_claims: number;
  verified_claims: number;
  hallucination_count: number;
  unverified_count: number;
  hallucination_rate: number;
  validity_score: number;
  taxonomy_distribution: Record<ValidationStatus, number>;
  confidence_by_label: Record<ValidationStatus, number>;
  avg_confidence: number;
}

// ── API Response shapes ───────────────────────────────────────────────────────

export interface UploadResponse {
  session_id: string;
  metadata: DatasetMetadata;
}

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

export interface AnalyzeResponse {
  session_id: string;
  status: "complete" | "error";
  metrics: Metrics;
  validation_results: ValidationResult[];
  ground_truth: GroundTruth;
}

export interface GroundTruth {
  summary: {
    stats: Record<string, unknown>;
    dtypes: Record<string, string>;
  };
  correlations: Correlation[];
  group_differences: GroupDifference[];
  categorical_associations: CategoricalAssociation[];
}

export interface Correlation {
  var1: string;
  var2: string;
  pearson: { r: number; p: number };
  spearman: { r: number; p: number };
  correlation: number;
  p_value: number;
  strength: string;
  direction: "positive" | "negative";
  confidence: number;
  type: "correlation";
}

export interface GroupDifference {
  var1: string;
  var2: string;
  variable: string;
  group_by: string;
  test: string;
  p_value: number;
  stat: number;
  effect_size: number;
  direction: string;
  significant: boolean;
  group_means: Record<string, number>;
  confidence: number;
  type: "group_difference";
}

export interface CategoricalAssociation {
  var1: string;
  var2: string;
  test: string;
  p_value: number;
  cramers_v: number;
  strength: string;
  direction: string;
  confidence: number;
  type: "categorical_association";
}

// ── Analyse request body ──────────────────────────────────────────────────────

export interface AnalyzeRequest {
  session_id: string;
  model_provider: "ollama" | "openai" | "anthropic";
  model_name?: string;
  use_csvl: boolean;
  num_insights: number;
  openai_key?: string;
  anthropic_key?: string;
}
