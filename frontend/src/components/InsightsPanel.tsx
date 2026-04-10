"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { usePrismaStore } from "@/store/prismaStore";
import { StatusBadge } from "./Dashboard";
import type { ValidationResult } from "@/lib/api";

const ALL_STATUSES = [
  "VALID",
  "HALLUCINATION_RELATIONSHIP",
  "HALLUCINATION_DIRECTION",
  "HALLUCINATION_MAGNITUDE",
  "HALLUCINATION_VARIABLE",
  "UNVERIFIED",
];

export function InsightsPanel() {
  const { validationResults, phase } = usePrismaStore();
  const [selected, setSelected] = useState<string[]>(ALL_STATUSES);
  const [expanded, setExpanded] = useState<number | null>(null);

  if (phase !== "complete") {
    return <Empty msg="Run an analysis to see generated insights." />;
  }

  const filtered = validationResults.filter((vr) => selected.includes(vr.status));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <h1 style={{ fontSize: "1.7rem", fontWeight: 800 }} className="gradient-text">
        Insights
      </h1>

      {/* Filter chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
        {ALL_STATUSES.map((s) => {
          const on = selected.includes(s);
          return (
            <button
              key={s}
              onClick={() =>
                setSelected((prev) =>
                  on ? prev.filter((x) => x !== s) : [...prev, s]
                )
              }
              style={{
                padding: "4px 12px",
                border: on ? "1px solid var(--brand)" : "1px solid var(--border)",
                borderRadius: 99,
                background: on ? "rgba(124,92,252,0.15)" : "transparent",
                color: on ? "var(--brand-light)" : "var(--text-muted)",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {s.replace("HALLUCINATION_", "H·")}
            </button>
          );
        })}
        <span style={{ color: "var(--text-muted)", fontSize: "0.78rem", alignSelf: "center", marginLeft: 4 }}>
          {filtered.length} / {validationResults.length}
        </span>
      </div>

      {/* Insight cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <AnimatePresence>
          {filtered.map((vr, i) => (
            <InsightCard
              key={i}
              index={i}
              vr={vr}
              expanded={expanded === i}
              onToggle={() => setExpanded(expanded === i ? null : i)}
            />
          ))}
        </AnimatePresence>
        {filtered.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center", padding: "2rem" }}>
            No insights match the selected filters.
          </div>
        )}
      </div>
    </div>
  );
}

// ── InsightCard ────────────────────────────────────────────────────────────

function InsightCard({
  index, vr, expanded, onToggle,
}: {
  index: number;
  vr: ValidationResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  const confPct = Math.round(vr.claim.confidence_score * 100);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.035 }}
      className="card"
      style={{ cursor: "pointer" }}
      onClick={onToggle}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: "0.8rem" }}>
        {/* Number */}
        <span
          style={{
            minWidth: 26,
            height: 26,
            borderRadius: "50%",
            background: "var(--bg-layer)",
            border: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "0.72rem",
            fontWeight: 700,
            color: "var(--text-muted)",
            flexShrink: 0,
            marginTop: 2,
          }}
        >
          {index + 1}
        </span>

        {/* Main content */}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
            <div style={{ fontSize: "0.88rem", fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>
              {vr.claim.original_text}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
              <StatusBadge status={vr.status} />
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--brand-light)" }}>
                {confPct}%
              </span>
              <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                {expanded ? "▲" : "▼"}
              </span>
            </div>
          </div>

          {/* Confidence bar */}
          <div style={{ height: 3, borderRadius: 99, background: "var(--border)", marginTop: 8 }}>
            <div
              style={{
                height: "100%",
                borderRadius: 99,
                width: `${confPct}%`,
                background: "linear-gradient(90deg, var(--brand), var(--brand-light))",
                transition: "width 0.4s ease",
              }}
            />
          </div>

          {/* Expanded details */}
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.22 }}
                style={{ overflow: "hidden" }}
              >
                <div
                  style={{
                    marginTop: "0.9rem",
                    paddingTop: "0.9rem",
                    borderTop: "1px solid var(--border)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  <Row label="Reason" value={vr.reason} />
                  <Row label="Direction" value={vr.claim.direction} />
                  <Row label="Strength" value={vr.claim.strength} />
                  {vr.extracted_vars.length > 0 && (
                    <Row label="Variables" value={vr.extracted_vars.join(", ")} />
                  )}
                  {vr.ground_truth && (
                    <div>
                      <span style={{ color: "var(--text-muted)", fontWeight: 600 }}>Ground Truth</span>
                      <pre
                        style={{
                          marginTop: 4,
                          padding: "0.6rem",
                          background: "var(--bg-layer)",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "0.72rem",
                          color: "var(--text-secondary)",
                          overflowX: "auto",
                        }}
                      >
                        {JSON.stringify(vr.ground_truth, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: "0.5rem" }}>
      <span style={{ color: "var(--text-muted)", fontWeight: 600, minWidth: 80 }}>{label}</span>
      <span style={{ color: "var(--text-secondary)" }}>{value || "—"}</span>
    </div>
  );
}

function Empty({ msg }: { msg: string }) {
  return (
    <div style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "5rem", fontSize: "0.88rem" }}>
      {msg}
    </div>
  );
}
