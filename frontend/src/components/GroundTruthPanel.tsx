"use client";

import { usePrismaStore } from "@/store/prismaStore";
import { motion } from "framer-motion";

export function GroundTruthPanel() {
  const { groundTruth, phase } = usePrismaStore();

  if (phase !== "complete" || !groundTruth) {
    return (
      <div style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "5rem", fontSize: "0.88rem" }}>
        Run an analysis to see the statistical ground truth.
      </div>
    );
  }

  const correlations = (groundTruth.correlations as Record<string, unknown>[]) ?? [];
  const groupDiffs = (groundTruth.group_differences as Record<string, unknown>[]) ?? [];
  const catAssocs = (groundTruth.categorical_associations as Record<string, unknown>[]) ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <h1 style={{ fontSize: "1.7rem", fontWeight: 800 }} className="gradient-text">
        Statistical Ground Truth
      </h1>

      {/* Correlations */}
      <Section title={`Correlations (${correlations.length})`}>
        {correlations.length === 0 ? (
          <Empty msg="No significant correlations found." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {correlations.map((c, i) => {
              const r = (c.pearson as { r: number })?.r ?? 0;
              const p = (c.pearson as { p: number })?.p ?? 1;
              const positive = r >= 0;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.8rem",
                    padding: "0.7rem 0.9rem",
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "0.82rem",
                  }}
                >
                  <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                    {String(c.var1)} ↔ {String(c.var2)}
                  </span>
                  <div style={{ marginLeft: "auto", display: "flex", gap: "1rem" }}>
                    <Chip label="r" value={r.toFixed(3)} color={positive ? "#22c55e" : "#ef4444"} />
                    <Chip label="p" value={p < 0.001 ? "<0.001" : p.toFixed(4)} color="var(--brand-light)" />
                    <Chip label="strength" value={String(c.strength)} color="var(--text-secondary)" />
                    <Chip
                      label="direction"
                      value={String(c.direction)}
                      color={positive ? "#22c55e" : "#ef4444"}
                    />
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </Section>

      {/* Group differences */}
      <Section title={`Group Differences (${groupDiffs.length})`}>
        {groupDiffs.length === 0 ? (
          <Empty msg="No significant group differences found." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {groupDiffs.map((d, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                style={{
                  padding: "0.7rem 0.9rem",
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "0.82rem",
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 4 }}>
                  {String(d.variable ?? d.var2)} by {String(d.group_by ?? d.var1)}
                </div>
                <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
                  <Chip label="test" value={String(d.test)} color="var(--text-muted)" />
                  <Chip label="p" value={Number(d.p_value).toFixed(4)} color="var(--brand-light)" />
                  <Chip label="effect" value={Number(d.effect_size).toFixed(3)} color="#a78bfa" />
                  <Chip label="direction" value={String(d.direction)} color="var(--text-secondary)" />
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </Section>

      {/* Categorical associations */}
      <Section title={`Categorical Associations (${catAssocs.length})`}>
        {catAssocs.length === 0 ? (
          <Empty msg="No significant categorical associations found." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {catAssocs.map((a, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                style={{
                  padding: "0.7rem 0.9rem",
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "0.82rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.8rem",
                }}
              >
                <span style={{ fontWeight: 700 }}>{String(a.var1)} ↔ {String(a.var2)}</span>
                <div style={{ marginLeft: "auto", display: "flex", gap: "1rem" }}>
                  <Chip label="Cramér's V" value={Number(a.cramers_v).toFixed(3)} color="#a855f7" />
                  <Chip label="p" value={Number(a.p_value).toFixed(4)} color="var(--brand-light)" />
                  <Chip label="strength" value={String(a.strength)} color="var(--text-secondary)" />
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)" }}>{title}</div>
      {children}
    </div>
  );
}

function Chip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ fontSize: "0.72rem" }}>
      <span style={{ color: "var(--text-muted)" }}>{label} </span>
      <span style={{ fontWeight: 700, color }}>{value}</span>
    </div>
  );
}

function Empty({ msg }: { msg: string }) {
  return <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{msg}</div>;
}
