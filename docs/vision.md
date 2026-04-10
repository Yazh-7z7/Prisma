# Prisma — Vision Document

> **Hallucination-Aware Insight Generation over Tabular Data**
> A production-grade, closed-loop, self-validating AI pipeline.

---

## Mission

Prisma solves a fundamental problem with LLM-generated analytics: **hallucination** — the tendency for language models to invent relationships, directions, and variable names that have no basis in the actual data.

The system accepts raw tabular datasets (CSV/XLSX), computes rigorous statistical ground truth, and runs a closed three-step LLM loop that generates, critiques, and refines insights before validating every claim against a six-category hallucination taxonomy.

---

## Architecture

```
Frontend (Next.js 14)  ←──HTTP──►  FastAPI Backend (Railway)
  - Sidebar                          POST /upload
  - Dashboard                        POST /analyze
  - InsightsPanel                    GET  /results
  - ValidationPanel
  - GroundTruthPanel
                                   ┌──────────────────────────┐
                                   │  data_ingestion.py       │
                                   │  stat_engine.py  (cached)│
                                   │  csvl_engine.py  (async) │
                                   │  parser.py               │
                                   │  validator.py            │
                                   │  reporting.py            │
                                   │  llm_client.py           │
                                   └──────────────────────────┘

shared/types.py + shared/types.ts  — single schema for both layers
```

---

## Directory Structure

```
Prisma/
├── backend/
│   ├── api_server.py
│   ├── data_ingestion.py
│   ├── stat_engine.py
│   ├── csvl_engine.py
│   ├── parser.py
│   ├── validator.py
│   ├── reporting.py
│   ├── llm_client.py
│   └── insight_generator.py   (preserved original)
├── frontend/
│   ├── src/app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── src/components/
│   │   ├── Sidebar.tsx
│   │   ├── Dashboard.tsx
│   │   ├── InsightsPanel.tsx
│   │   ├── ValidationPanel.tsx
│   │   └── GroundTruthPanel.tsx
│   ├── src/lib/api.ts
│   ├── src/store/prismaStore.ts
│   ├── package.json
│   ├── next.config.js
│   └── tsconfig.json
├── src/              (Streamlit modules — preserved, unchanged)
├── app.py            (Streamlit UI — preserved)
├── shared/
│   ├── types.py
│   └── types.ts
├── config/
├── datasets/
├── docs/
│   └── vision.md
├── requirements.txt
├── connectionlog.txt
└── readme.md
```

---

## Core Concepts

### CSVL — Closed-Loop Self-Validating LLM

```
Step 1: GENERATE   → LLM produces initial numbered insight list
Step 2: CRITIQUE   → LLM audits each insight against statistical ground truth
Step 3: REFINE     → LLM corrects/removes hallucinated claims
         ↓
Standard Parse → Validate pipeline
```

### Hallucination Taxonomy

| Label | Description |
|---|---|
| VALID | Supported by statistical ground truth |
| HALLUCINATION_RELATIONSHIP | Claimed relationship does not exist in data |
| HALLUCINATION_DIRECTION | Direction (positive/negative) is incorrect |
| HALLUCINATION_MAGNITUDE | Strength significantly overstated/understated |
| HALLUCINATION_VARIABLE | References a non-existent column name |
| UNVERIFIED | Cannot be verified against available evidence |

### Confidence Formula

```
confidence = 0.6 * (1 - p_value) + 0.4 * |correlation|
Clipped to [0.01, 0.99]
```

---

## LLM Provider Support

| Provider | Notes |
|---|---|
| Ollama (default) | Local, no API key. Requires `ollama serve` |
| OpenAI | Set OPENAI_API_KEY or pass runtime key |
| Anthropic | Set ANTHROPIC_API_KEY or pass runtime key |

---

## Deployment

| Layer | Platform | Command |
|---|---|---|
| FastAPI Backend | Railway | `uvicorn backend.api_server:app --host 0.0.0.0 --port $PORT` |
| Next.js Frontend | Vercel | Root: frontend/, Build: `npm run build` |
| Streamlit (legacy) | Any | `streamlit run app.py` |

---

## Phased Implementation Plan

### Phase 1 — Core Backend Foundation [COMPLETE]
- data_ingestion.py — CSV/XLSX ingest with multi-encoding support
- stat_engine.py — Pearson, Spearman, t-test, ANOVA, chi-square + lru_cache
- csvl_engine.py — async three-step Generate → Critique → Refine loop
- parser.py — handles numbered lists, bullets, and markdown headings
- validator.py — six-category taxonomy with grounded confidence formula
- reporting.py — JSON + Markdown report generation
- llm_client.py — pluggable Ollama/OpenAI/Anthropic dispatcher
- api_server.py — FastAPI: POST /upload, POST /analyze, GET /results
- requirements.txt — consolidated with FastAPI, uvicorn, pydantic

### Phase 2 — Type System & Connection Registry [COMPLETE]
- shared/types.py — Python type definitions
- shared/types.ts — TypeScript mirror for the frontend
- connectionlog.txt — master connection and endpoint registry

### Phase 3 — Next.js Frontend [COMPLETE]
- Global CSS design system (dark premium, glassmorphism, CSS tokens)
- Zustand global store
- Typed API client (src/lib/api.ts)
- Sidebar — upload, model config, CSVL toggle, run button
- Dashboard — metric cards, donut chart, confidence bars, summary table
- InsightsPanel — filterable insight cards with expandable ground truth
- ValidationPanel — taxonomy legend + full detail table
- GroundTruthPanel — correlations, group diffs, categorical associations
- Framer Motion animated transitions

### Phase 4 — Deployment Configuration [COMPLETE]
- next.config.js with API rewrite proxy
- .env.local for local dev
- Railway start command documented in connectionlog.txt
- Vercel build settings documented in connectionlog.txt

### Phase 5 — Optimisation & Polish [NEXT]
- [ ] Redis session store (replace in-memory _SESSIONS dict)
- [ ] Streaming LLM responses via Server-Sent Events
- [ ] Rate limiting and queuing on heavy LLM calls
- [ ] Frontend: CSV/PDF export from dashboard
- [ ] Frontend: D3-based correlation heatmap
- [ ] Frontend: column selector for targeted insight generation
- [ ] Automated test suite (pytest + Jest)
- [ ] CI/CD: GitHub Actions → Railway + Vercel auto-deploy

### Phase 6 — Production Hardening [FUTURE]
- [ ] PostgreSQL for persistent session storage
- [ ] JWT authentication layer
- [ ] Batch analysis (multiple datasets per session)
- [ ] Dataset versioning and diff-analysis
- [ ] Custom prompt templates via UI editor
- [ ] Multi-user workspace isolation

---

## Change Log

| Date | Change |
|---|---|
| 2026-04-10 | Initial production scaffold: FastAPI backend (6 modules), Next.js frontend (5 components), shared types, connectionlog.txt, vision.md |

---

*This document is the living reference for the Prisma project. Update the Change Log and Phase 5/6 checklist as work progresses.*
