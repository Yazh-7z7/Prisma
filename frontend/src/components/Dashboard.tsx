"use client";

import React from "react";
import { usePrismaStore } from "@/store/prismaStore";
import { motion } from "framer-motion";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from "recharts";

// ── Colour map ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  VALID: "#22c55e",
  HALLUCINATION_RELATIONSHIP: "#ef4444",
  HALLUCINATION_DIRECTION: "#f97316",
  HALLUCINATION_MAGNITUDE: "#eab308",
  HALLUCINATION_VARIABLE: "#a855f7",
  UNVERIFIED: "#6b7280",
  DESCRIPTIVE_INCORRECT: "#06b6d4",
};

const STATUS_LABELS: Record<string, string> = {
  VALID: "Valid",
  HALLUCINATION_RELATIONSHIP: "Relationship",
  HALLUCINATION_DIRECTION: "Direction",
  HALLUCINATION_MAGNITUDE: "Magnitude",
  HALLUCINATION_VARIABLE: "Variable",
  UNVERIFIED: "Unverified",
  DESCRIPTIVE_INCORRECT: "Descriptive (incorrect)",
};

const DashboardIcons = {
  total: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>,
  valid: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>,
  warning: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>,
  rate: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>,
  shield: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>,
  brain: <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"></path><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"></path></svg>,
};


// ── Dashboard ──────────────────────────────────────────────────────────────

export function Dashboard() {
  const { phase, metrics, validationResults, metadata, fileName } = usePrismaStore();

  if (!metrics) return null;

  const pieData = Object.entries(metrics.taxonomy_distribution)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, label: STATUS_LABELS[name] ?? name }));

  // Confidence box data per status
  const boxData = Object.entries(
    validationResults.reduce<Record<string, number[]>>((acc, vr) => {
      const s = vr.status;
      if (!acc[s]) acc[s] = [];
      acc[s].push(vr.claim?.confidence_score ?? 0);
      return acc;
    }, {})
  ).map(([name, vals]) => {
    const sorted = [...vals].sort((a, b) => a - b);
    const q1 = sorted[Math.floor(sorted.length * 0.25)] ?? 0;
    const q3 = sorted[Math.floor(sorted.length * 0.75)] ?? 0;
    const med = sorted[Math.floor(sorted.length * 0.5)] ?? 0;
    return { name: STATUS_LABELS[name] ?? name, rawName: name, min: sorted[0] ?? 0, max: sorted[sorted.length - 1] ?? 0, q1, q3, med };
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.7rem", fontWeight: 800, letterSpacing: "-0.5px" }} className="gradient-text">
          Dashboard
        </h1>
        <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 4 }}>
          {fileName} · {metadata?.rows?.toLocaleString()} rows · {metadata?.columns} columns
        </div>
      </div>

      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "1rem" }}>
        {[
          { label: "Total Claims", value: metrics.total_claims, color: "var(--text-primary)", icon: DashboardIcons.total },
          { label: "Valid Claims", value: metrics.valid_claims, color: "var(--valid)", icon: DashboardIcons.valid },
          { label: "Hallucinations", value: metrics.hallucination_count, color: "var(--h-relationship)", icon: DashboardIcons.warning },
          { label: "Hallucination Rate", value: `${metrics.hallucination_rate ?? 0}%`, color: "var(--h-direction)", icon: DashboardIcons.rate },
          { label: "Validity Score", value: `${metrics.validity_score ?? 0}%`, color: "var(--valid)", icon: DashboardIcons.shield },
          { label: "Avg Confidence", value: (metrics.avg_confidence ?? 0).toFixed(2), color: "var(--h-variable)", icon: DashboardIcons.brain },
        ].map((m, i) => (
          <motion.div
            key={m.label}
            className="card"
            style={{ borderBottom: `3px solid ${m.color}`, position: "relative", overflow: "hidden" }}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <div style={{ position: "absolute", top: "-15px", right: "-15px", width: "90px", height: "90px", opacity: 0.04, pointerEvents: "none", color: "var(--text-primary)" }}>
              {m.icon}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: 6 }}>
              <div style={{ width: "16px", height: "16px", color: m.color, flexShrink: 0 }}>
                {m.icon}
              </div>
              <div style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", fontWeight: 700 }}>
                {m.label}
              </div>
            </div>
            <div style={{ fontSize: "1.85rem", fontWeight: 900, color: m.color, letterSpacing: "-1px" }}>
              {m.value}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        {/* Donut chart */}
        <motion.div
          className="card"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.25 }}
        >
          <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "0.9rem" }}>
            Taxonomy Distribution
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={95}
                paddingAngle={3}
                dataKey="value"
              >
                {pieData.map((entry, idx) => (
                  <Cell key={idx} fill={STATUS_COLORS[entry.name] ?? "#888"} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8 }}
                formatter={(v: any, _: any, p: any) => [v, p.payload.label]}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Legend */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem 1rem", marginTop: 4 }}>
            {pieData.map((d) => (
              <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "0.72rem" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: STATUS_COLORS[d.name] ?? "#888", display: "inline-block" }} />
                {d.label}: {d.value}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Box plot (simplified with bar) */}
        <motion.div
          className="card"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.32 }}
        >
          <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "0.9rem" }}>
            Confidence by Category
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {boxData.map((d) => {
              const pct = Math.round(d.med * 100);
              return (
                <div key={d.name}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: 3 }}>
                    <span style={{ color: "var(--text-secondary)" }}>{d.name}</span>
                    <span style={{ color: "var(--brand-light)", fontWeight: 600 }}>{pct}%</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.06)" }}>
                    <motion.div
                      style={{ height: "100%", borderRadius: 3, background: STATUS_COLORS[d.rawName] ?? "var(--brand)" }}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: 0.4, duration: 0.6, ease: "easeOut" }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Insights summary table */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.42 }}
      >
        <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "0.9rem" }}>
          All Insights — Summary
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
            <thead>
              <tr style={{ color: "var(--text-muted)", textAlign: "left" }}>
                {["#", "Claim", "Status", "Confidence"].map((h) => (
                  <th key={h} style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)", fontWeight: 600 }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {validationResults.map((vr, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    transition: "background 0.12s",
                  }}
                >
                  <td style={{ padding: "8px 10px", color: "var(--text-muted)" }}>{i + 1}</td>
                  <td style={{ padding: "8px 10px", maxWidth: 420, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {vr.claim?.original_text ?? ""}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    <StatusBadge status={vr.status} />
                  </td>
                  <td style={{ padding: "8px 10px", color: "var(--brand-light)", fontWeight: 600 }}>
                    {(vr.claim?.confidence_score ?? 0).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}



// ── Status badge ──────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "#888888";
  return (
    <span
      className="badge"
      style={{
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
      }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
