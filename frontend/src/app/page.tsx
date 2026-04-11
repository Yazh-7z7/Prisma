"use client";

import React, { useState, useCallback } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/components/Dashboard";
import { InsightsPanel } from "@/components/InsightsPanel";
import { ValidationPanel } from "@/components/ValidationPanel";
import { GroundTruthPanel } from "@/components/GroundTruthPanel";
import { usePrismaStore } from "@/store/prismaStore";
import { motion, AnimatePresence } from "framer-motion";
import { useDropzone } from "react-dropzone";
import { api } from "@/lib/api";

export default function Home() {
  const {
    phase, activeTab,
    fileName,
    modelProvider, modelName,
    useCsvl, numInsights,
    sessionId, error,
    setUploadResult, setAnalyzing, setAnalyzeResult, setError,
    setModelProvider, setModelName, setUseCsvl, setNumInsights
  } = usePrismaStore();

  const [started, setStarted] = useState(false);
  const [uploading, setUploading] = useState(false);

  const panels: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    insights: <InsightsPanel />,
    validation: <ValidationPanel />,
    "ground-truth": <GroundTruthPanel />,
  };

  // ── Dropzone & Run Handlers ──
  const onDrop = useCallback(
    async (accepted: File[]) => {
      if (!accepted.length) return;
      const file = accepted[0];
      setUploading(true);
      try {
        const res = await api.upload(file);
        setUploadResult(res, file.name);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [setUploadResult, setError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    maxFiles: 1,
    disabled: uploading,
  });

  const handleRun = async () => {
    if (!sessionId) return;
    setAnalyzing();
    try {
      const res = await api.analyze({
        session_id: sessionId,
        model_provider: modelProvider,
        model_name: modelName || undefined,
        use_csvl: useCsvl,
        num_insights: numInsights,
      });
      setAnalyzeResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
    }
  };

  // ── Render ──

  if (phase === "idle" && !started) {
    // 1. INTRO PAGE
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", textAlign: "center", gap: "1.5rem" }}>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }}>
          <div style={{ fontSize: "6rem", fontWeight: 900, letterSpacing: "-4px", lineHeight: 1 }} className="gradient-text">
            PRISMA
          </div>
          <div style={{ fontSize: "1.2rem", color: "var(--text-secondary)", marginTop: "1rem", maxWidth: 500, marginInline: "auto" }}>
            Hallucination-aware insight generation with a<br />
            <strong style={{ color: "var(--brand)" }}>Closed-Loop Self-Validating LLM</strong> pipeline.
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} style={{ display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center", marginTop: "1rem" }}>
          {["Upload CSV/XLSX", "Statistical Ground Truth", "CSVL Pipeline", "5-Category Taxonomy"].map((step) => (
            <div key={step} style={{ padding: "0.6rem 1.2rem", background: "var(--bg-layer)", border: "1px solid var(--border)", borderRadius: 99, fontSize: "0.85rem", color: "var(--text-secondary)", boxShadow: "0 2px 4px rgba(0,0,0,0.02)" }}>
              {step}
            </div>
          ))}
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.55 }} style={{ marginTop: "2rem" }}>
          <button className="btn-primary" onClick={() => setStarted(true)} style={{ fontSize: "1.05rem", padding: "0.9rem 2.5rem" }}>
            Get Started →
          </button>
        </motion.div>
      </div>
    );
  }

  if (phase !== "complete") {
    // 2. INPUT / QUILLBOT STYLE PAGE
    return (
      <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", alignItems: "center", paddingTop: "12vh" }}>
        
        <div style={{ marginBottom: "3rem", textAlign: "center" }}>
          <h1 style={{ fontSize: "2.5rem", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-1px" }}>
            Ready to make something <span style={{ color: "var(--brand)" }}>amazing</span>?
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem", marginTop: "0.5rem" }}>
            Upload your dataset to begin hallucination-free analysis.
          </p>
        </div>

        <div className="card" style={{ width: "100%", maxWidth: 640, padding: "2rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
          
          {phase === "analyzing" ? (
             <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "3rem 0", gap: "1.5rem" }}>
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                style={{ width: 56, height: 56, borderRadius: "50%", border: "4px solid var(--border)", borderTopColor: "var(--brand)" }}
              />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontWeight: 700, fontSize: "1.2rem", color: "var(--text-primary)", marginBottom: 6 }}>Running Prisma Pipeline</div>
                <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Generating → Critiquing → Refining → Validating…</div>
              </div>
            </div>
          ) : (
            <>
              {/* Giant Dropzone */}
              <div
                {...getRootProps()}
                style={{
                  border: `2px dashed ${isDragActive ? "var(--brand)" : "var(--border-strong)"}`,
                  borderRadius: "var(--radius-lg)",
                  padding: "3rem 2rem",
                  textAlign: "center",
                  cursor: "pointer",
                  background: isDragActive ? "rgba(239,68,68,0.04)" : "var(--bg-base)",
                  transition: "all 0.2s",
                }}
              >
                <input {...getInputProps()} />
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "1rem" }}>
                  <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--bg-layer)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--brand)" }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                  </div>
                  <div style={{ textAlign: "left" }}>
                    {uploading ? (
                      <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Uploading...</div>
                    ) : fileName ? (
                      <div style={{ fontWeight: 600, color: "var(--brand)" }}>✓ {fileName} uploaded</div>
                    ) : (
                      <>
                        <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "1.1rem" }}>Click or drag a file</div>
                        <div style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>CSV or Excel files supported</div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Settings Row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1.5rem", padding: "0 0.5rem" }}>
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: 8 }}>Model</div>
                  <select className="input" value={modelProvider} onChange={(e) => setModelProvider(e.target.value as any)}>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </div>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase" }}>Insights</div>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--brand)" }}>{numInsights}</div>
                  </div>
                  <input
                    type="range"
                    min={5} max={20}
                    value={numInsights}
                    onChange={(e) => setNumInsights(Number(e.target.value))}
                    style={{ width: "100%", accentColor: "var(--brand)", marginTop: 6 }}
                  />
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: 8 }}>CSVL Mode</div>
                  <button
                    onClick={() => setUseCsvl(!useCsvl)}
                    style={{
                      height: 42,
                      width: "100%",
                      borderRadius: "var(--radius-md)",
                      border: `1px solid ${useCsvl ? "var(--brand)" : "var(--border)"}`,
                      background: useCsvl ? "rgba(239,68,68,0.08)" : "var(--bg-layer)",
                      color: useCsvl ? "var(--brand)" : "var(--text-secondary)",
                      fontWeight: 600,
                      cursor: "pointer",
                      transition: "all 0.2s"
                    }}
                  >
                    {useCsvl ? "Enabled ✅" : "Disabled"}
                  </button>
                </div>
              </div>

              {/* Error and Run */}
              {error && <div style={{ color: "#ef4444", background: "#fef2f2", padding: "0.75rem", borderRadius: "8px", fontSize: "0.9rem", textAlign: "center" }}>{error}</div>}
              
              <button 
                className="btn-primary"
                disabled={phase !== "uploaded"}
                onClick={handleRun}
                style={{ padding: "1rem", fontSize: "1.1rem" }}
              >
                Generate Verified Insights
              </button>
            </>
          )}

        </div>
      </div>
    );
  }

  // 3. DASHBOARD PAGE
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)" }}>
      <Sidebar />
      <main
        style={{
          flex: 1,
          padding: "2.5rem 3rem",
          overflowY: "auto",
          minHeight: "100vh",
          position: "relative",
          zIndex: 1,
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
          >
            {panels[activeTab]}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
