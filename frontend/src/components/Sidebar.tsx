"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { usePrismaStore } from "@/store/prismaStore";
import { api } from "@/lib/api";

// ── Nav items ─────────────────────────────────────────────────────────────

const NAV = [
  { id: "dashboard",    label: "Dashboard",     icon: "⬡" },
  { id: "insights",     label: "Insights",      icon: "💡" },
  { id: "validation",   label: "Validation",    icon: "✦" },
  { id: "ground-truth", label: "Ground Truth",  icon: "◈" },
] as const;

// ── Sidebar ───────────────────────────────────────────────────────────────

export function Sidebar() {
  const {
    phase, error,
    fileName, metadata,
    modelProvider, modelName,
    useCsvl, numInsights,
    openaiKey, anthropicKey,
    activeTab,
    sessionId,
    setUploadResult, setAnalyzing, setAnalyzeResult, setError,
    setModelProvider, setModelName, setUseCsvl, setNumInsights,
    setOpenaiKey, setAnthropicKey, setActiveTab, reset,
  } = usePrismaStore();

  const [uploading, setUploading] = useState(false);

  // ── Drop zone ──────────────────────────────────────────────────────────
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

  // ── Run analysis ───────────────────────────────────────────────────────
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
        openai_key: openaiKey || undefined,
        anthropic_key: anthropicKey || undefined,
      });
      setAnalyzeResult(res);
      setActiveTab("dashboard");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
    }
  };

  const canRun = (phase === "uploaded" || phase === "complete") && !uploading;
  const isAnalyzing = phase === "analyzing";

  return (
    <aside
      style={{
        width: 280,
        minHeight: "100vh",
        background: "var(--bg-layer)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "1.5rem 1.25rem",
        gap: "1.5rem",
        position: "sticky",
        top: 0,
        height: "100vh",
        overflowY: "auto",
      }}
    >
      {/* Logo */}
      <div>
        <div
          style={{
            fontSize: "1.7rem",
            fontWeight: 900,
            letterSpacing: "-1px",
            background: "linear-gradient(135deg,#fff 0%,#a78bfa 60%,#7c5cfc 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          PRISMA
        </div>
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 2 }}>
          Hallucination-Aware AI Insights
        </div>
      </div>

      {/* Nav */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {NAV.map((item) => {
          const active = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.65rem",
                padding: "0.6rem 0.9rem",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: active ? "rgba(124,92,252,0.15)" : "transparent",
                color: active ? "var(--brand-light)" : "var(--text-secondary)",
                fontWeight: active ? 600 : 400,
                fontSize: "0.875rem",
                cursor: "pointer",
                width: "100%",
                textAlign: "left",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              <span style={{ fontSize: "1rem" }}>{item.icon}</span>
              {item.label}
              {active && (
                <span style={{ marginLeft: "auto", width: 4, height: 4, borderRadius: "50%", background: "var(--brand)" }} />
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ height: 1, background: "var(--border)" }} />

      {/* Upload zone */}
      <div>
        <Label>Dataset</Label>
        <div
          {...getRootProps()}
          style={{
            border: `1px dashed ${isDragActive ? "var(--brand)" : "var(--border-strong)"}`,
            borderRadius: "var(--radius-md)",
            padding: "1.2rem",
            textAlign: "center",
            cursor: "pointer",
            background: isDragActive ? "rgba(124,92,252,0.07)" : "transparent",
            transition: "all 0.2s",
            marginTop: 6,
          }}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>Uploading…</span>
          ) : fileName ? (
            <span style={{ color: "var(--brand-light)", fontSize: "0.8rem", fontWeight: 600 }}>
              ✓ {fileName}
            </span>
          ) : (
            <span style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
              Drop CSV / XLSX or click
            </span>
          )}
        </div>
        {metadata && (
          <div style={{ marginTop: 6, fontSize: "0.72rem", color: "var(--text-muted)" }}>
            {metadata.rows.toLocaleString()} rows · {metadata.columns} cols
          </div>
        )}
      </div>

      {/* Model config */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <Label>LLM Provider</Label>
        <select
          className="input"
          value={modelProvider}
          onChange={(e) => setModelProvider(e.target.value as typeof modelProvider)}
        >
          <option value="ollama">Ollama (Local)</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
        </select>

        <Label>Model Name</Label>
        <input
          className="input"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
          placeholder={
            modelProvider === "ollama"
              ? "gemma:2b"
              : modelProvider === "openai"
              ? "gpt-4-turbo"
              : "claude-3-sonnet-20240229"
          }
        />

        {modelProvider === "openai" && (
          <>
            <Label>OpenAI API Key</Label>
            <input
              className="input"
              type="password"
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              placeholder="sk-..."
            />
          </>
        )}
        {modelProvider === "anthropic" && (
          <>
            <Label>Anthropic API Key</Label>
            <input
              className="input"
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder="sk-ant-..."
            />
          </>
        )}
      </div>

      {/* Settings */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <Label style={{ marginBottom: 0 }}>CSVL Mode</Label>
            <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 1 }}>
              Self-Validating Loop
            </div>
          </div>
          <Toggle value={useCsvl} onChange={setUseCsvl} />
        </div>

        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Label style={{ marginBottom: 0 }}>Insights</Label>
            <span style={{ fontSize: "0.78rem", color: "var(--brand-light)", fontWeight: 600 }}>
              {numInsights}
            </span>
          </div>
          <input
            type="range"
            min={5}
            max={20}
            value={numInsights}
            onChange={(e) => setNumInsights(Number(e.target.value))}
            style={{ width: "100%", marginTop: 6, accentColor: "var(--brand)" }}
          />
        </div>
      </div>

      <div style={{ height: 1, background: "var(--border)" }} />

      {/* Error */}
      {error && (
        <div style={{
          background: "rgba(239,68,68,0.12)",
          border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: "var(--radius-sm)",
          padding: "0.6rem 0.8rem",
          fontSize: "0.75rem",
          color: "#fca5a5",
        }}>
          {error}
        </div>
      )}

      {/* Run button */}
      <button
        className="btn-primary"
        disabled={!canRun || isAnalyzing}
        onClick={handleRun}
        style={{ width: "100%", justifyContent: "center" }}
      >
        {isAnalyzing ? (
          <>
            <span className="animate-spin" style={{ display: "inline-block" }}>⟳</span>
            Analyzing…
          </>
        ) : (
          <>▶  Run Analysis</>
        )}
      </button>

      {phase !== "idle" && (
        <button className="btn-ghost" onClick={reset} style={{ width: "100%", justifyContent: "center" }}>
          Reset
        </button>
      )}

      {/* Footer */}
      <div style={{ marginTop: "auto", fontSize: "0.65rem", color: "var(--text-muted)", textAlign: "center" }}>
        Prisma v1.0 · Hallucination-Aware AI
      </div>
    </aside>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function Label({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        fontSize: "0.72rem",
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        color: "var(--text-muted)",
        marginBottom: 4,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Toggle({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      className="toggle-track"
      onClick={() => onChange(!value)}
      style={{ background: value ? "var(--brand)" : "#2a2a44" }}
      aria-pressed={value}
      aria-label="Toggle CSVL mode"
    >
      <motion.div
        className="toggle-thumb"
        animate={{ x: value ? 20 : 0 }}
        transition={{ type: "spring", stiffness: 600, damping: 30 }}
      />
    </button>
  );
}
