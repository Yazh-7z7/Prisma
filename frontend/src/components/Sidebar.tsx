"use client";

import React from "react";
import { usePrismaStore } from "@/store/prismaStore";

const Icons = {
  dashboard: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
  ),
  insights: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
  ),
  validation: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
  ),
  groundTruth: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
  )
};

const NAV = [
  { id: "dashboard",    label: "Dashboard",     icon: Icons.dashboard },
  { id: "insights",     label: "Insights",      icon: Icons.insights },
  { id: "validation",   label: "Validation",    icon: Icons.validation },
  { id: "ground-truth", label: "Ground Truth",  icon: Icons.groundTruth },
] as const;

export function Sidebar() {
  const { activeTab, setActiveTab, reset } = usePrismaStore();

  return (
    <aside
      style={{
        width: 260,
        minHeight: "100vh",
        background: "var(--bg-layer)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "2rem 1.5rem",
        gap: "2rem",
        position: "sticky",
        top: 0,
        height: "100vh",
        overflowY: "auto",
      }}
    >
      {/* Logo */}
      <div style={{ paddingLeft: "0.5rem" }}>
        <div
          style={{
            fontSize: "1.75rem",
            fontWeight: 800,
            letterSpacing: "-1px",
            color: "var(--brand)",
          }}
        >
          PRISMA
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2, fontWeight: 500 }}>
          Hallucination-Aware AI
        </div>
      </div>

      {/* Nav */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {NAV.map((item) => {
          const active = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.75rem 1rem",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: active ? "var(--bg-card-hover)" : "transparent",
                color: active ? "var(--brand)" : "var(--text-secondary)",
                fontWeight: active ? 600 : 500,
                fontSize: "0.9rem",
                cursor: "pointer",
                width: "100%",
                textAlign: "left",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ display: "flex", color: active ? "var(--brand)" : "currentcolor" }}>
                {item.icon}
              </div>
              {item.label}
            </button>
           );
        })}
      </nav>

      <div style={{ height: 1, background: "var(--border)" }} />

      <button className="btn-ghost" onClick={reset} style={{ width: "100%", justifyContent: "center" }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
        New Dataset
      </button>

      {/* Footer */}
      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textAlign: "center" }}>
        Prisma v1.0
      </div>
    </aside>
  );
}
