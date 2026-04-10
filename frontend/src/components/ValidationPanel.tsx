"use client";

import { usePrismaStore } from "@/store/prismaStore";
import { motion } from "framer-motion";
import { StatusBadge } from "./Dashboard";

const TAXONOMY_ORDER = [
  "VALID",
  "HALLUCINATION_RELATIONSHIP",
  "HALLUCINATION_DIRECTION",
  "HALLUCINATION_MAGNITUDE",
  "HALLUCINATION_VARIABLE",
  "UNVERIFIED",
];

const TAXONOMY_DESC: Record<string, string> = {
  VALID: "Claim is fully supported by statistical ground truth.",
  HALLUCINATION_RELATIONSHIP: "A relationship is claimed that does not exist in the data.",
  HALLUCINATION_DIRECTION: "The direction of a relationship is incorrect (e.g. positive vs negative).",
  HALLUCINATION_MAGNITUDE: "The strength of a relationship is significantly overstated or understated.",
  HALLUCINATION_VARIABLE: "The claim references a column name that does not exist in the dataset.",
  UNVERIFIED: "The claim cannot be verified against available statistical evidence.",
};

export function ValidationPanel() {
  const { validationResults, metrics, phase } = usePrismaStore();

  if (phase !== "complete" || !metrics) {
    return <Empty />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <h1 style={{ fontSize: "1.7rem", fontWeight: 800 }} className="gradient-text">
        Validation Breakdown
      </h1>

      {/* Taxonomy legend */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "0.75rem" }}>
        {TAXONOMY_ORDER.map((status) => {
          const count = metrics.taxonomy_distribution[status] ?? 0;
          const avgConf = metrics.confidence_by_label[status] ?? 0;
          return (
            <motion.div
              key={status}
              className="card"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ display: "flex", flexDirection: "column", gap: 6 }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <StatusBadge status={status} />
                <span style={{ fontWeight: 800, fontSize: "1.2rem" }}>{count}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {TAXONOMY_DESC[status]}
              </div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>
                Avg confidence: <strong style={{ color: "var(--brand-light)" }}>{(avgConf * 100).toFixed(0)}%</strong>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Detailed table */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <div style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "0.9rem" }}>
          All Claims — Detailed View
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.79rem" }}>
            <thead>
              <tr style={{ color: "var(--text-muted)", textAlign: "left" }}>
                {["#", "Claim", "Status", "Confidence", "Reason"].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: "8px 10px",
                      borderBottom: "1px solid var(--border)",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {validationResults.map((vr, i) => (
                <tr
                  key={i}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td style={{ padding: "8px 10px", color: "var(--text-muted)" }}>{i + 1}</td>
                  <td style={{ padding: "8px 10px", maxWidth: 300, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {vr.claim.original_text}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    <StatusBadge status={vr.status} />
                  </td>
                  <td style={{ padding: "8px 10px", color: "var(--brand-light)", fontWeight: 700 }}>
                    {(vr.claim.confidence_score * 100).toFixed(0)}%
                  </td>
                  <td style={{ padding: "8px 10px", color: "var(--text-muted)", maxWidth: 260, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {vr.reason}
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

function Empty() {
  return (
    <div style={{ color: "var(--text-muted)", textAlign: "center", marginTop: "5rem", fontSize: "0.88rem" }}>
      Run an analysis to see validation results.
    </div>
  );
}
