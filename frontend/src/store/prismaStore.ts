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
export const DEFAULT_MODEL_BY_PROVIDER = {
  ollama: "gemma:2b",
  groq: "llama-3.1-8b-instant",
  gemini: "gemini-1.5-flash",
} as const;

interface PrismaState {
  phase: AppPhase;
  error: string | null;

  // Upload
  sessionId: string | null;
  metadata: DatasetMetadata | null;
  fileName: string | null;

  // Settings
  modelProvider: "ollama" | "groq" | "gemini";
  modelName: string;
  useCsvl: boolean;
  numInsights: number;
  groqKey: string;
  geminiKey: string;
  theme: "light" | "dark";

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
  setModelProvider: (p: "ollama" | "groq" | "gemini") => void;
  setModelName: (n: string) => void;
  setUseCsvl: (v: boolean) => void;
  setNumInsights: (n: number) => void;
  setGroqKey: (k: string) => void;
  setGeminiKey: (k: string) => void;
  setActiveTab: (t: PrismaState["activeTab"]) => void;
  toggleTheme: () => void;
}

export const usePrismaStore = create<PrismaState>()((set) => ({
  phase: "idle",
  error: null,
  sessionId: null,
  metadata: null,
  fileName: null,
  modelProvider: "ollama",
  modelName: DEFAULT_MODEL_BY_PROVIDER.ollama,
  useCsvl: true,
  numInsights: 10,
  groqKey: "",
  geminiKey: "",
  theme: "light",
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
      validationResults: [],
      metrics: null,
      groundTruth: null,
      activeTab: "dashboard",
      error: null,
    }),

  setAnalyzing: () => set({ phase: "analyzing", error: null }),

  setAnalyzeResult: (res) =>
    set({
      phase: "complete",
      validationResults: res.validation_results,
      metrics: res.metrics,
      groundTruth: res.ground_truth,
      activeTab: "dashboard",
      error: null,
    }),

  setError: (msg) =>
    set((state) => ({
      phase: state.sessionId ? "uploaded" : "error",
      error: msg,
    })),

  reset: () =>
    set({
      phase: "idle",
      error: null,
      sessionId: null,
      metadata: null,
      fileName: null,
      modelProvider: "ollama",
      modelName: DEFAULT_MODEL_BY_PROVIDER.ollama,
      useCsvl: true,
      numInsights: 10,
      validationResults: [],
      metrics: null,
      groundTruth: null,
      activeTab: "dashboard",
    }),

  setModelProvider: (p) =>
    set({
      modelProvider: p,
      modelName: DEFAULT_MODEL_BY_PROVIDER[p],
      error: null,
    }),
  setModelName: (n) => set({ modelName: n }),
  setUseCsvl: (v) => set({ useCsvl: v }),
  setNumInsights: (n) => set({ numInsights: n }),
  setGroqKey: (k) => set({ groqKey: k }),
  setGeminiKey: (k) => set({ geminiKey: k }),
  setActiveTab: (t) => set({ activeTab: t }),
  toggleTheme: () => set((state) => {
    const newTheme = state.theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", newTheme);
    return { theme: newTheme };
  }),
}));
