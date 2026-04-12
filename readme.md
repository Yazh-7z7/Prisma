# Prisma — Hallucination-Aware Insight Generator

<div align="center">

**A production-grade, closed-loop self-validating pipeline for generating statistically grounded insights from tabular data — with built-in hallucination detection.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-prisma--xi--seven.vercel.app-6366f1?style=for-the-badge&logo=vercel)](https://prisma-xi-seven.vercel.app/)
[![Backend](https://img.shields.io/badge/Backend-Railway-0B0D0E?style=for-the-badge&logo=railway)](https://railway.app)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2014-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

</div>

---

## What is Prisma?

Most LLMs hallucinate. When applied to data analysis, this means confidently stating false statistics — a serious problem in any real-world decision pipeline.

**Prisma** solves this by coupling LLM insight generation with a rigorous statistical ground truth engine. Every claim produced by the model is automatically parsed, looked up against pre-computed statistics, and classified as **Valid**, **Unverified**, or **Hallucination** before reaching the user.

---

## System Architecture

```
CSV / XLSX Upload
       │
       ▼
┌─────────────────┐     ┌─────────────────────────────┐
│  Data Ingestion │────▶│  Statistical Engine          │
└─────────────────┘     │  (Pearson, Spearman, T-test, │
                        │  ANOVA, Chi-Square, IQR)     │
                        └────────────┬────────────────-┘
                                     │  Ground Truth
                        ┌────────────▼────────────────-┐
                        │  CSVL Engine                  │
                        │  (Closed-Loop Self-Validation)│
                        │  LLM → Parse → Validate → Loop│
                        └────────────┬────────────────-┘
                                     │  Validated Claims
                        ┌────────────▼────────────────-┐
                        │  Report Generator             │
                        │  Metrics: HR, Precision,      │
                        │  Recall, F1                   │
                        └─────────────────────────────-┘
```

---

## Key Features

### 🔁 Closed-Loop Self-Validation (CSVL)
The core differentiator. The pipeline doesn't just generate insights — it loops: generate → parse → validate → regenerate if hallucination rate is too high. This ensures the final output meets a quality threshold before being returned.

### 📊 Statistical Ground Truth Engine
Computed before any LLM call, giving the validator hard evidence:
- **Pearson & Spearman** correlations with p-value significance
- **T-test & ANOVA** for group difference claims
- **Chi-Square** for categorical associations
- **Z-score & IQR** for distribution/outlier claims

### 🧠 Multi-Provider LLM Support
| Provider | Models |
|---|---|
| **Groq** | `llama-3.3-70b-versatile`, `mixtral-8x7b` |
| **Gemini** | `gemini-1.5-flash`, `gemini-1.5-pro` |
| **Ollama** | Any local model (`llama3`, `mistral`, etc.) |

### 🏷️ Hallucination Classification
Every insight is labeled:
- ✅ **VALID** — Statistically supported (p < 0.05, correct direction)
- ⚠️ **UNVERIFIED** — Variables not found or relationship too complex to validate
- ❌ **HALLUCINATION** — Directly contradicted by the data

### 📈 Metrics Dashboard
After each run, Prisma reports:
- **Hallucination Rate** (HR)
- **Precision & Recall** of valid insights
- **F1 Score**
- Full per-insight breakdown with evidence

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, TypeScript, Framer Motion, Recharts, Zustand |
| **Backend** | FastAPI, Uvicorn, Pydantic v2 |
| **Statistics** | pandas, numpy, scipy, statsmodels, scikit-learn |
| **Deployment** | Vercel (frontend) + Railway (backend) |

---

## Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Groq or Gemini API key (or Ollama running locally)

### 1. Clone the repo

```bash
git clone https://github.com/Yazh-7z7/Prisma.git
cd Prisma
```

### 2. Backend Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the root:

```env
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
```

Start the backend:

```bash
uvicorn backend.api_server:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 3. Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Open `http://localhost:3000`

---

## Deployment

| Service | Platform | URL |
|---|---|---|
| Frontend | Vercel | [prisma-xi-seven.vercel.app](https://prisma-xi-seven.vercel.app/) |
| Backend | Railway | Set `NEXT_PUBLIC_API_URL` to your Railway domain |

**Required environment variables:**

**Railway (Backend):**
```
GROQ_API_KEY=...
GEMINI_API_KEY=...
```

**Vercel (Frontend):**
```
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/providers/status` | Check which LLM providers are configured |
| `POST` | `/upload` | Upload CSV/XLSX, returns `session_id` |
| `POST` | `/analyze` | Run the full pipeline on a session |
| `GET` | `/results?session_id=...` | Fetch cached results |

Full interactive docs at `/docs` (Swagger UI).

---

## Project Structure

```
Prisma/
├── backend/
│   ├── api_server.py        # FastAPI app & routes
│   ├── stat_engine.py       # Statistical ground truth engine
│   ├── csvl_engine.py       # Closed-loop self-validation pipeline
│   ├── validator.py         # Claim → ground truth verifier
│   ├── parser.py            # NLP claim extraction
│   ├── llm_client.py        # Unified LLM provider client
│   ├── data_ingestion.py    # CSV/XLSX loader & metadata
│   └── reporting.py        # Metrics & report generation
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # Dashboard, Sidebar, Panels
│   │   ├── lib/             # API client (axios)
│   │   └── store/           # Zustand state management
│   └── next.config.js
├── requirements.txt
├── Procfile                 # Railway start command
└── .env                    # Local secrets (not committed)
```

---

## Validation Logic

A claim is classified as a **Hallucination** if:
> The LLM asserts a relationship or statistic that is either **statistically insignificant** (p > 0.05) or **directionally wrong** compared to the computed ground truth.

| Claim Type | Test Used | Example |
|---|---|---|
| Correlation | Pearson/Spearman | *"Age is strongly correlated with BMI"* |
| Group Difference | T-test / ANOVA | *"Smokers have higher glucose levels"* |
| Association | Chi-Square | *"Gender is associated with work type"* |
| Descriptive | Mean/Median/Count | *"Average glucose level is 106.14"* |

---

## License

MIT
