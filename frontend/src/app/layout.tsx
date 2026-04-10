import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Prisma — Hallucination-Aware Insight Generation",
  description:
    "Closed-Loop Self-Validating pipeline for hallucination detection and insight generation over tabular data.",
  keywords: ["AI", "hallucination detection", "data analysis", "LLM", "Prisma"],
  authors: [{ name: "Prisma" }],
  openGraph: {
    title: "Prisma",
    description: "Hallucination-aware AI insight generation over tabular data.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
