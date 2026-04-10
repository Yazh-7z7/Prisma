// frontend/src/store/prismaStore.ts
// Zustand global store — single source of truth for the dashboard.

import { create } from "zustand";
import type {
  UploadResponse,
  AnalyzeResponse,
  ValidationResult,
  Metrics,
  DatasetMetadata,
} from "@/lib/api";

export type AppPhase = "idle" | "uploaded" | "analyzing" | "complete" | "error";

interface PrismaState {
  phase: AppPhase;
  error: string | null;

  // Upload
  sessionId: string | null;
  metadata: DatasetMetadata | null;
  fileName: string | null;

  // Settings
  modelProvider: "ollama" | "openai" | "anthropic";
  modelName: string;
  useCsvl: boolean;
  numInsights: number;
  openaiKey: string;
  anthropicKey: string;

  // Results
  validationResults: ValidationResult[];
  metrics: Metrics | null;
  groundTruth: Record<string, unknown> | null;

  // Active tab
  activeTab: "dashboard" | "insights" | "validation" | "ground-truth";

  // Actions
  setUploadResult: (res: UploadResponse, fileName: string) => void;
  setAnalyzing: () => void;
  setAnalyzeResult: (res: AnalyzeResponse) => void;
  setError: (msg: string) => void;
  reset: () => void;
  setModelProvider: (p: "ollama" | "openai" | "anthropic") => void;
  setModelName: (n: string) => void;
  setUseCsvl: (v: boolean) => void;
  setNumInsights: (n: number) => void;
  setOpenaiKey: (k: string) => void;
  setAnthropicKey: (k: string) => void;
  setActiveTab: (t: PrismaState["activeTab"]) => void;
}

export const usePrismaStore = create<PrismaState>()((set) => ({
  phase: "idle",
  error: null,
  sessionId: null,
  metadata: null,
  fileName: null,
  modelProvider: "ollama",
  modelName: "gemma:2b",
  useCsvl: true,
  numInsights: 10,
  openaiKey: "",
  anthropicKey: "",
  validationResults: [],
  metrics: null,
  groundTruth: null,
  activeTab: "dashboard",

  setUploadResult: (res, fileName) =>
    set({
      phase: "uploaded",
      sessionId: res.session_id,
      metadata: res.metadata,
      fileName,
      error: null,
    }),

  setAnalyzing: () => set({ phase: "analyzing", error: null }),

  setAnalyzeResult: (res) =>
    set({
      phase: "complete",
      validationResults: res.validation_results,
      metrics: res.metrics,
      groundTruth: res.ground_truth,
      error: null,
    }),

  setError: (msg) => set({ phase: "error", error: msg }),

  reset: () =>
    set({
      phase: "idle",
      error: null,
      sessionId: null,
      metadata: null,
      fileName: null,
      validationResults: [],
      metrics: null,
      groundTruth: null,
    }),

  setModelProvider: (p) => set({ modelProvider: p }),
  setModelName: (n) => set({ modelName: n }),
  setUseCsvl: (v) => set({ useCsvl: v }),
  setNumInsights: (n) => set({ numInsights: n }),
  setOpenaiKey: (k) => set({ openaiKey: k }),
  setAnthropicKey: (k) => set({ anthropicKey: k }),
  setActiveTab: (t) => set({ activeTab: t }),
}));
