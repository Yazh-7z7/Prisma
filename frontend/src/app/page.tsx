"use client";

import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/components/Dashboard";
import { InsightsPanel } from "@/components/InsightsPanel";
import { ValidationPanel } from "@/components/ValidationPanel";
import { GroundTruthPanel } from "@/components/GroundTruthPanel";
import { usePrismaStore } from "@/store/prismaStore";
import { motion, AnimatePresence } from "framer-motion";

export default function Home() {
  const activeTab = usePrismaStore((s) => s.activeTab);

  const panels: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    insights: <InsightsPanel />,
    validation: <ValidationPanel />,
    "ground-truth": <GroundTruthPanel />,
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />

      {/* Main content */}
      <main
        style={{
          flex: 1,
          padding: "2rem",
          overflowY: "auto",
          minHeight: "100vh",
          position: "relative",
          zIndex: 1,
        }}
      >
        {/* Ambient gradient blob */}
        <div
          style={{
            position: "fixed",
            top: "-10%",
            right: "-5%",
            width: "50vw",
            height: "50vh",
            background:
              "radial-gradient(circle, rgba(124,92,252,0.12) 0%, transparent 70%)",
            pointerEvents: "none",
            zIndex: 0,
          }}
        />

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            style={{ position: "relative", zIndex: 1 }}
          >
            {panels[activeTab]}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
