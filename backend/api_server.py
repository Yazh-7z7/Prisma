"""
api_server.py — FastAPI Application
Prisma | Production-Grade Backend

Endpoints:
  POST  /upload     → ingest dataset, return metadata + session_id
  POST  /analyze    → run full pipeline (stat → LLM → CSVL → parse → validate → report)
  GET   /results    → return cached results for a session_id

Run:
  uvicorn backend.api_server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import time
import uuid
from functools import lru_cache
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Make sure backend/ can resolve its own siblings regardless of working dir
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Also expose src/ so shared modules are importable
_SRC = os.path.join(os.path.dirname(_HERE), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from data_ingestion import ingest_file, DataIngestionError
from stat_engine import analyze as stat_analyze
from csvl_engine import run_csvl_pipeline
from parser import parse_insights
from validator import validate_claims
from reporting import compute_metrics, generate_report
from llm_client import LLMClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Prisma.API")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Prisma API",
    description=(
        "Closed-Loop Self-Validating pipeline for hallucination-aware "
        "insight generation over tabular data."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Vercel frontend (and local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store (swap for Redis/DB in production)
# ---------------------------------------------------------------------------
_SESSIONS: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Shared LLM client (initialised once from env vars)
# ---------------------------------------------------------------------------
_llm_client: LLMClient | None = None


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(
            provider=os.getenv("DEFAULT_LLM_PROVIDER", "ollama"),
            openai_key=os.getenv("OPENAI_API_KEY"),
            anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    return _llm_client


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    session_id: str = Field(..., description="Session ID returned by /upload")
    model_provider: str = Field(default="ollama", description="ollama | openai | anthropic")
    model_name: str | None = Field(default=None, description="Model name within the provider")
    use_csvl: bool = Field(default=True, description="Enable Closed-Loop Self-Validation")
    num_insights: int = Field(default=10, ge=1, le=30)
    openai_key: str | None = Field(default=None, description="Optional runtime OpenAI key")
    anthropic_key: str | None = Field(default=None, description="Optional runtime Anthropic key")


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["Health"])
async def root():
    return {"status": "ok", "version": app.version}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return {"status": "ok", "version": app.version}


# ---- /upload ---------------------------------------------------------------

@app.post("/upload", tags=["Pipeline"])
async def upload_dataset(file: UploadFile = File(...)):
    """
    Accept a CSV or XLSX file.
    Returns a session_id plus dataset metadata.
    """
    filename = file.filename or "upload"
    content = await file.read()

    try:
        df, metadata = ingest_file(filename, content)
    except DataIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during upload")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")

    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "df": df,
        "metadata": metadata,
        "ground_truth": None,
        "results": None,
        "status": "uploaded",
        "created_at": time.time(),
    }

    logger.info("Session %s created for '%s'", session_id, filename)
    return {"session_id": session_id, "metadata": metadata}


# ---- /analyze --------------------------------------------------------------

@app.post("/analyze", tags=["Pipeline"])
async def analyze(body: AnalyzeRequest):
    """
    Run the full Prisma pipeline:
      1. Statistical ground truth
      2. LLM insight generation (with optional CSVL loop)
      3. Parse → Validate → Report
    """
    session = _SESSIONS.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please /upload first.")

    df: pd.DataFrame = session["df"]

    # --- Update LLM keys if provided at runtime ---
    llm = _get_llm_client()
    if body.openai_key:
        llm.update_key("openai", body.openai_key)
    if body.anthropic_key:
        llm.update_key("anthropic", body.anthropic_key)

    try:
        # 1. Statistical analysis (cached)
        logger.info("[%s] Step 1 — statistical analysis", body.session_id)
        ground_truth = stat_analyze(df)
        session["ground_truth"] = ground_truth

        # 2. Compact summary for LLM prompt
        dataset_summary = _build_summary(df, ground_truth)

        # 3. LLM generation (sync from executor so we don't block)
        logger.info("[%s] Step 2 — LLM generation (CSVL=%s)", body.session_id, body.use_csvl)

        if body.use_csvl:
            llm_output = await run_csvl_pipeline(
                ground_truth=ground_truth,
                dataset_summary=dataset_summary,
                llm_client=llm,
                model_provider=body.model_provider,
                model_name=body.model_name,
            )
        else:
            llm_output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: llm.generate(
                    _direct_prompt(dataset_summary),
                    provider=body.model_provider,
                    model=body.model_name,
                ),
            )

        if not llm_output:
            raise ValueError("LLM returned an empty response.")

        # 4. Parse
        logger.info("[%s] Step 3 — parsing insights", body.session_id)
        claims = parse_insights(llm_output)

        # 5. Validate
        logger.info("[%s] Step 4 — validating claims", body.session_id)
        validation_results = validate_claims(claims, ground_truth, list(df.columns))

        # 6. Metrics + report
        metrics = compute_metrics(validation_results)
        dataset_name = session["metadata"].get("filename", "dataset")
        model_name = body.model_name or body.model_provider
        report_paths = generate_report(
            validation_results, metrics, dataset_name, model_name
        )

        # Store in session
        session["results"] = {
            "validation_results": validation_results,
            "metrics": metrics,
            "ground_truth": ground_truth,
            "report_paths": report_paths,
            "llm_output": llm_output,
            "model_provider": body.model_provider,
            "model_name": model_name,
            "use_csvl": body.use_csvl,
        }
        session["status"] = "complete"

        return _serialize({
            "session_id": body.session_id,
            "status": "complete",
            "metrics": metrics,
            "validation_results": validation_results,
            "ground_truth": ground_truth,
        })

    except Exception as exc:
        logger.exception("[%s] Analysis failed", body.session_id)
        session["status"] = "error"
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


# ---- /results --------------------------------------------------------------

@app.get("/results", tags=["Pipeline"])
async def get_results(session_id: str = Query(...)):
    """
    Return cached results for a completed analysis session.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "complete":
        return {"session_id": session_id, "status": session["status"]}

    return _serialize({
        "session_id": session_id,
        "status": "complete",
        **session["results"],
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_summary(df: pd.DataFrame, ground_truth: dict[str, Any]) -> str:
    """Build a compact but information-rich summary string for the LLM."""
    parts = [f"Dataset: {df.shape[0]} rows × {df.shape[1]} columns"]
    parts.append(f"Columns: {', '.join(df.columns)}")

    # Brief describe
    try:
        desc = df.describe(include="number").to_string()
        parts.append(f"Numeric statistics:\n{desc[:800]}")
    except Exception:
        pass

    # Top correlations
    corrs = ground_truth.get("correlations", [])[:5]
    if corrs:
        parts.append("Top correlations:")
        for c in corrs:
            parts.append(
                f"  {c['var1']} vs {c['var2']}: r={c['pearson']['r']:.2f}, "
                f"p={c['pearson']['p']:.4f} ({c['strength']})"
            )

    return "\n".join(parts)


def _direct_prompt(summary: str) -> str:
    return (
        f"You are a data analyst.\n\n"
        f"Dataset summary:\n{summary}\n\n"
        "Generate exactly 10 concise, specific insights as a numbered list (1. ... 2. ...).\n"
        "Name the variables involved in each insight."
    )


def _serialize(obj: Any) -> Any:
    """Recursively make an object JSON-serialisable."""
    return json.loads(json.dumps(obj, default=str))
