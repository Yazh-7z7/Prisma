"use client";

import { usePrismaStore } from "@/store/prismaStore";
import { motion } from "framer-motion";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BoxPlot, ComposedChart, YAxis, XAxis, CartesianGrid,
} from "recharts";

// ── Colour map ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  VALID: "#22c55e",
  HALLUCINATION_RELATIONSHIP: "#ef4444",
  HALLUCINATION_DIRECTION: "#f97316",
  HALLUCINATION_MAGNITUDE: "#eab308",
  HALLUCINATION_VARIABLE: "#a855f7",
  UNVERIFIED: "#6b7280",
};

const STATUS_LABELS: Record<string, string> = {
  VALID: "Valid",
  HALLUCINATION_RELATIONSHIP: "Relationship",
  HALLUCINATION_DIRECTION: "Direction",
  HALLUCINATION_MAGNITUDE: "Magnitude",
  HALLUCINATION_VARIABLE: "Variable",
  UNVERIFIED: "Unverified",
};

// ── Dashboard ──────────────────────────────────────────────────────────────

export function Dashboard() {
  const { phase, metrics, validationResults, metadata, fileName } = usePrismaStore();

  if (phase === "idle" || phase === "uploaded") {
    return <LandingHero />;
  }

  if (phase === "analyzing") {
    return <Loader />;
  }

  if (!metrics) return null;

  const pieData = Object.entries(metrics.taxonomy_distribution)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, label: STATUS_LABELS[name] ?? name }));

  // Confidence box data per status
  const boxData = Object.entries(
    validationResults.reduce<Record<string, number[]>>((acc, vr) => {
      const s = vr.status;
      if (!acc[s]) acc[s] = [];
      acc[s].push(vr.claim.confidence_score);
      return acc;
    }, {})
  ).map(([name, vals]) => {
    const sorted = [...vals].sort((a, b) => a - b);
    const q1 = sorted[Math.floor(sorted.length * 0.25)];
    const q3 = sorted[Math.floor(sorted.length * 0.75)];
    const med = sorted[Math.floor(sorted.length * 0.5)];
    return { name: STATUS_LABELS[name] ?? name, min: sorted[0], max: sorted[sorted.length - 1], q1, q3, med };
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
          { label: "Total Claims", value: metrics.total_claims, color: "var(--text-primary)" },
          { label: "Valid Claims", value: metrics.valid_claims, color: "#22c55e" },
          { label: "Hallucinations", value: metrics.hallucination_count, color: "#ef4444" },
          { label: "Hallucination Rate", value: `${metrics.hallucination_rate}%`, color: "#f97316" },
          { label: "Validity Score", value: `${metrics.validity_score}%`, color: "#22c55e" },
          { label: "Avg Confidence", value: metrics.avg_confidence.toFixed(2), color: "var(--brand-light)" },
        ].map((m, i) => (
          <motion.div
            key={m.label}
            className="card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <div style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 6 }}>
              {m.label}
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: 800, color: m.color }}>
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
                formatter={(v: number, _: string, p: { payload: { label: string } }) => [v, p.payload.label]}
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
              const color = Object.entries(STATUS_LABELS).find(([, v]) => v === d.name)?.[0];
              return (
                <div key={d.name}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: 3 }}>
                    <span style={{ color: "var(--text-secondary)" }}>{d.name}</span>
                    <span style={{ color: "var(--brand-light)", fontWeight: 600 }}>{pct}%</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.06)" }}>
                    <motion.div
                      style={{ height: "100%", borderRadius: 3, background: STATUS_COLORS[color ?? ""] ?? "var(--brand)" }}
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
                    {vr.claim.original_text}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    <StatusBadge status={vr.status} />
                  </td>
                  <td style={{ padding: "8px 10px", color: "var(--brand-light)", fontWeight: 600 }}>
                    {vr.claim.confidence_score.toFixed(2)}
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

// ── Landing hero ───────────────────────────────────────────────────────────

function LandingHero() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "80vh",
        textAlign: "center",
        gap: "1.5rem",
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div
          style={{
            fontSize: "5rem",
            fontWeight: 900,
            letterSpacing: "-3px",
            lineHeight: 1,
          }}
          className="gradient-text"
        >
          PRISMA
        </div>
        <div style={{ fontSize: "1.1rem", color: "var(--text-secondary)", marginTop: "0.8rem", maxWidth: 440 }}>
          Hallucination-aware insight generation with a<br />
          <strong style={{ color: "var(--brand-light)" }}>Closed-Loop Self-Validating LLM</strong> pipeline.
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        style={{
          display: "flex",
          gap: "1rem",
          flexWrap: "wrap",
          justifyContent: "center",
          marginTop: "1rem",
        }}
      >
        {["Upload CSV/XLSX", "Statistical Ground Truth", "CSVL Pipeline", "5-Category Taxonomy"].map((step) => (
          <div
            key={step}
            style={{
              padding: "0.5rem 1.1rem",
              border: "1px solid var(--border-strong)",
              borderRadius: 99,
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
            }}
          >
            {step}
          </div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: "0.5rem" }}
      >
        ← Upload a dataset from the sidebar to get started
      </motion.div>
    </div>
  );
}

// ── Loader ────────────────────────────────────────────────────────────────

function Loader() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "70vh", gap: "1.5rem" }}>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
        style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          border: "3px solid var(--border)",
          borderTopColor: "var(--brand)",
        }}
      />
      <div style={{ textAlign: "center" }}>
        <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: 4 }}>Running Prisma Pipeline</div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>
          Generating → Critiquing → Refining → Validating…
        </div>
      </div>
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "#888";
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
