"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/components/Dashboard";
import { InsightsPanel } from "@/components/InsightsPanel";
import { ValidationPanel } from "@/components/ValidationPanel";
import { GroundTruthPanel } from "@/components/GroundTruthPanel";
import Prism from "@/components/Prism";
import TargetCursor from "@/components/TargetCursor";
import { DEFAULT_MODEL_BY_PROVIDER, usePrismaStore } from "@/store/prismaStore";
import { motion, AnimatePresence } from "framer-motion";
import { useDropzone } from "react-dropzone";
import { api, type ProviderStatusResponse } from "@/lib/api";

const PROVIDER_OPTIONS = [
  {
    id: "ollama",
    label: "Ollama",
    short: "Local",
    description: "Fast local iteration with your downloaded model.",
  },
  {
    id: "groq",
    label: "Groq",
    short: "Hosted",
    description: "Ultra-fast inference powered by LPU.",
  },
  {
    id: "gemini",
    label: "Gemini",
    short: "Hosted",
    description: "Self-validating analysis with Google Gemini.",
  },
] as const;

const PIPELINE_STEPS = [
  "Upload CSV/XLSX",
  "Compute Ground Truth",
  "Run CSVL Loop",
  "Validate Every Claim",
] as const;

const ANALYSIS_STEPS = [
  "Statistical ground truth",
  "Insight generation",
  "Self-critique and refinement",
  "Validation and scoring",
] as const;

function FloatingThemeToggle({ theme, toggleTheme }: { theme: "light" | "dark", toggleTheme: () => void }) {
  return (
    <button
      onClick={toggleTheme}
      className="cursor-target"
      style={{
        position: "absolute",
        top: "2rem",
        right: "2rem",
        background: "var(--bg-layer)",
        border: "1px solid var(--border)",
        color: "var(--text-secondary)",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "40px",
        height: "40px",
        borderRadius: "50%",
        boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
        zIndex: 100,
        transition: "all 0.2s"
      }}
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      onMouseOver={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.transform = "scale(1.05)"; }}
      onMouseOut={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; e.currentTarget.style.transform = "scale(1)"; }}
    >
      {theme === "light" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
      )}
    </button>
  );
}

export default function Home() {
  const {
    phase,
    activeTab,
    fileName,
    metadata,
    modelProvider,
    modelName,
    useCsvl,
    numInsights,
    sessionId,
    error,
    setUploadResult,
    setAnalyzing,
    setAnalyzeResult,
    setError,
    setModelProvider,
    setModelName,
    setUseCsvl,
    setNumInsights,
    theme,
    toggleTheme,
  } = usePrismaStore();

  const [started, setStarted] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [providerStatus, setProviderStatus] = useState<ProviderStatusResponse | null>(null);

  const panels: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    insights: <InsightsPanel />,
    validation: <ValidationPanel />,
    "ground-truth": <GroundTruthPanel />,
  };

  const selectedProvider = useMemo(
    () => PROVIDER_OPTIONS.find((provider) => provider.id === modelProvider) ?? PROVIDER_OPTIONS[0],
    [modelProvider]
  );
  const prismTone = theme === "dark"
    ? {
        hueShift: -0.18,
        glow: 1.28,
        noise: 0.05,
        colorFrequency: 1.08,
        bloom: 1.18,
      }
    : {
        hueShift: -0.08,
        glow: 1.06,
        noise: 0.07,
        colorFrequency: 0.92,
        bloom: 1.02,
      };

  const runDisabled = !sessionId || uploading || phase === "analyzing";
  const insightDensity = Math.round(((numInsights - 5) / 15) * 100);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    let active = true;
    api.providerStatus()
      .then((res) => {
        if (active) setProviderStatus(res);
      })
      .catch(() => {
        if (active) setProviderStatus(null);
      });

    return () => {
      active = false;
    };
  }, []);

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
    accept: {
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    maxFiles: 1,
    disabled: uploading || phase === "analyzing",
  });

  const handleRun = async () => {
    if (!sessionId) return;
    setAnalyzing();
    try {
      const res = await api.analyze({
        session_id: sessionId,
        model_provider: modelProvider,
        model_name: modelName || DEFAULT_MODEL_BY_PROVIDER[modelProvider],
        use_csvl: useCsvl,
        num_insights: numInsights,
      });
      setAnalyzeResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
    }
  };

  if (phase === "idle" && !started) {
    return (
      <div className="landing-shell">
        <Prism
          className="prism-backdrop"
          animationType="3drotate"
          timeScale={0.32}
          scale={4.4}
          hoverStrength={1.2}
          transparent
          suspendWhenOffscreen
          {...prismTone}
        />
        <TargetCursor targetSelector=".cursor-target" />
        <FloatingThemeToggle theme={theme} toggleTheme={toggleTheme} />
        <div className="landing-orb landing-orb-one" />
        <div className="landing-orb landing-orb-two" />

        <div className="landing-content" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", textAlign: "center", gap: "1.5rem", padding: "2rem" }}>
          <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.55 }}>
            <div style={{ fontSize: "6rem", fontWeight: 900, letterSpacing: "-4px", lineHeight: 1 }} className="gradient-text cursor-target">
              PRISMA
            </div>
            <div style={{ fontSize: "1.15rem", color: "var(--text-secondary)", marginTop: "1rem", maxWidth: 620, marginInline: "auto" }}>
              Hallucination-aware insight generation for tabular data with a
              {" "}
              <strong style={{ color: "var(--brand-deep)" }}>closed-loop self-validating pipeline</strong>
              {" "}
              grounded in statistical truth.
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.28 }} className="signal-row">
            {PIPELINE_STEPS.map((step) => (
              <div key={step} className="signal-pill cursor-target">
                {step}
              </div>
            ))}
          </motion.div>

          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.52 }} style={{ marginTop: "1.5rem" }}>
            <button className="btn-primary cursor-target" onClick={() => setStarted(true)} style={{ fontSize: "1.05rem", padding: "0.95rem 2.75rem" }}>
              Start Grounded Analysis
            </button>
          </motion.div>
        </div>
      </div>
    );
  }

  if (phase !== "complete") {
    return (
      <div className="workspace-shell">
        <Prism
          className="prism-backdrop"
          animationType="hover"
          timeScale={0.24}
          scale={4}
          hoverStrength={1.4}
          transparent
          suspendWhenOffscreen
          {...prismTone}
        />
        <FloatingThemeToggle theme={theme} toggleTheme={toggleTheme} />
        <div className="landing-orb landing-orb-one" />
        <div className="landing-orb landing-orb-two" />

        <div className="workspace-content">
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
              <div className="hero-kicker">Closed-loop self-validating analytics</div>
              <h1 className="workspace-title cursor-target">
                Ground every insight in
                {" "}
                <span className="gradient-text">data, not guesswork.</span>
              </h1>
              <p className="workspace-subtitle">
                Upload a dataset, compute statistical ground truth, and let Prisma generate
                evidence-backed insights that are critiqued, refined, and validated before you trust them.
              </p>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="signal-row" style={{ justifyContent: "center", marginTop: "1.5rem" }}>
              {PIPELINE_STEPS.map((step) => (
                <div key={step} className="signal-pill cursor-target">
                  {step}
                </div>
              ))}
            </motion.div>
          </div>

          <div className="workspace-card">
            {phase === "analyzing" ? (
              <div className="analyzing-shell">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }}
                  style={{ width: 62, height: 62, borderRadius: "50%", border: "4px solid rgba(255,255,255,0.66)", borderTopColor: "var(--brand)", boxShadow: "0 12px 30px rgba(239,68,68,0.18)" }}
                />
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontWeight: 800, fontSize: "1.3rem", color: "var(--text-primary)", marginBottom: 6 }}>
                    Running the Prisma pipeline
                  </div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
                    Generating grounded signals, auditing them against truth, and returning validated insights.
                  </div>
                </div>

                <div className="analysis-steps">
                  {ANALYSIS_STEPS.map((step, index) => (
                    <motion.div
                      key={step}
                      className="analysis-step"
                      initial={{ opacity: 0.35, x: -10 }}
                      animate={{ opacity: [0.45, 1, 0.45], x: 0 }}
                      transition={{ duration: 1.5, repeat: Infinity, delay: index * 0.16 }}
                    >
                      <span className="analysis-step-index">0{index + 1}</span>
                      <span>{step}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="hero-grid">
                  <div
                    {...getRootProps()}
                    className="upload-zone cursor-target"
                    data-active={isDragActive || Boolean(fileName)}
                  >
                    <input {...getInputProps()} />

                    <div className="upload-icon">
                      {uploading ? (
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
                          style={{ width: 22, height: 22, borderRadius: "50%", border: "2px solid rgba(239,68,68,0.25)", borderTopColor: "var(--brand)" }}
                        />
                      ) : (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="17 8 12 3 7 8"></polyline>
                          <line x1="12" y1="3" x2="12" y2="15"></line>
                        </svg>
                      )}
                    </div>

                    <div>
                      {uploading ? (
                        <>
                          <div className="upload-title">Uploading your dataset...</div>
                          <div className="upload-subtitle">Prisma is reading the file and preparing metadata.</div>
                        </>
                      ) : fileName ? (
                        <>
                          <div className="upload-title">{fileName}</div>
                          <div className="upload-subtitle">Dataset attached and ready for grounded analysis.</div>
                        </>
                      ) : (
                        <>
                          <div className="upload-title">Drop your dataset here or browse files</div>
                          <div className="upload-subtitle">Supports CSV and XLSX. Prisma will compute statistical ground truth before any LLM output is accepted.</div>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="context-panel cursor-target">
                    <div className="context-panel-title">Pipeline context</div>
                    <div className="context-panel-copy">
                      {useCsvl
                        ? "CSVL mode is active, so Prisma will generate, critique, and refine insights before validation."
                        : "CSVL mode is off, so Prisma will run a faster direct generation pass before validation."}
                    </div>

                    <div className="dataset-stats">
                      <StatPill label="Rows" value={metadata?.rows?.toLocaleString() ?? "Waiting"} />
                      <StatPill label="Columns" value={metadata?.columns?.toString() ?? "Waiting"} />
                      <StatPill label="Numeric" value={metadata?.numeric_columns?.length?.toString() ?? "Waiting"} />
                      <StatPill label="Missing" value={metadata?.missing_total?.toLocaleString?.() ?? "Waiting"} />
                    </div>
                  </div>
                </div>

                <div className="control-grid">
                  <div className="control-card">
                    <div className="control-header">
                      <div>
                        <div className="control-label">Model Provider</div>
                        <div className="control-caption">Choose where Prisma should generate insights.</div>
                      </div>
                    </div>

                    <div className="provider-grid">
                      {PROVIDER_OPTIONS.map((provider) => {
                        const active = provider.id === modelProvider;
                        return (
                          <button
                            key={provider.id}
                            type="button"
                            className="provider-card cursor-target"
                            data-active={active}
                            onClick={() => setModelProvider(provider.id)}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem" }}>
                              <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>{provider.label}</span>
                              <span className="provider-badge">{provider.short}</span>
                            </div>
                            <div style={{ fontSize: "0.82rem", color: active ? "var(--text-primary)" : "var(--text-secondary)" }}>
                              {provider.description}
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    <div className="provider-detail-grid">
                      <div>
                        <div className="control-label" style={{ marginBottom: 8 }}>Model ID</div>
                        <input
                          className="input cursor-target"
                          value={modelName}
                          onChange={(e) => setModelName(e.target.value)}
                          placeholder={DEFAULT_MODEL_BY_PROVIDER[modelProvider]}
                        />
                        <div className="input-hint">
                          Default for {selectedProvider.label}: {DEFAULT_MODEL_BY_PROVIDER[modelProvider]}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="control-card">
                    <div className="control-header">
                      <div>
                        <div className="control-label">Analysis Controls</div>
                        <div className="control-caption">Tune how many insights Prisma should produce and how strict the loop should be.</div>
                      </div>
                    </div>

                    <div className="slider-header">
                      <div>
                        <div className="control-label">Verified insights target</div>
                        <div className="control-caption">Higher counts increase coverage, but also ask the model to stretch further.</div>
                      </div>
                      <div className="slider-value">{numInsights}</div>
                    </div>

                    <input
                      type="range"
                      min={5}
                      max={20}
                      value={numInsights}
                      onChange={(e) => setNumInsights(Number(e.target.value))}
                      className="range-input"
                    />
                    <div className="range-meter">
                      <motion.div
                        className="range-meter-fill"
                        animate={{ width: `${Math.max(insightDensity, 8)}%` }}
                        transition={{ duration: 0.25, ease: "easeOut" }}
                      />
                    </div>

                    <button
                      type="button"
                      className="csvl-toggle cursor-target"
                      data-on={useCsvl}
                      onClick={() => setUseCsvl(!useCsvl)}
                    >
                      <div>
                        <div className="control-label">CSVL Mode</div>
                        <div className="control-caption">
                          {useCsvl ? "Generate → critique → refine before validation." : "Faster direct generation with validation only."}
                        </div>
                      </div>

                      <motion.div
                        className="csvl-switch"
                        animate={{ backgroundColor: useCsvl ? "rgba(239,68,68,0.18)" : "rgba(15,23,42,0.08)" }}
                        transition={{ duration: 0.25 }}
                      >
                        <motion.div
                          className="csvl-switch-thumb"
                          animate={{ x: useCsvl ? 28 : 0 }}
                          transition={{ type: "spring", stiffness: 420, damping: 26 }}
                        />
                      </motion.div>
                    </button>

                    <div className="csvl-state-banner" data-on={useCsvl}>
                      <span className="csvl-state-dot" />
                      <span>
                        {useCsvl
                          ? "CSVL is active. Prisma will self-correct weak or fabricated claims before final validation."
                          : "CSVL is paused. Use this when you want the fastest pass or you are comparing raw provider behavior."}
                      </span>
                    </div>
                  </div>
                </div>

                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      className="error-panel"
                    >
                      <div className="error-panel-title">Analysis needs attention</div>
                      <div className="error-panel-copy">{error}</div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="run-row">
                  <div className="run-meta">
                    <div className="run-meta-title">
                      {fileName ? "Dataset ready" : "Awaiting dataset"}
                    </div>
                    <div className="run-meta-copy">
                      {fileName
                        ? `${selectedProvider.label} will generate insights with ${useCsvl ? "CSVL safeguards" : "direct validation only"} using ${modelName || DEFAULT_MODEL_BY_PROVIDER[modelProvider]}.`
                        : "Upload a dataset to unlock grounded insight generation."}
                    </div>
                  </div>

                  <button className="btn-primary cursor-target" disabled={runDisabled} onClick={handleRun} style={{ padding: "1rem 1.5rem", fontSize: "1rem", minWidth: 230 }}>
                    Generate Grounded Insights
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)", position: "relative", overflow: "hidden" }}>
      <Prism
        className="prism-backdrop prism-backdrop-dashboard"
        animationType="rotate"
        timeScale={0.18}
        scale={4.8}
        hoverStrength={0}
        transparent
        suspendWhenOffscreen
        {...prismTone}
      />
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

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="dataset-stat-pill cursor-target">
      <span className="dataset-stat-label">{label}</span>
      <span className="dataset-stat-value">{value}</span>
    </div>
  );
}
