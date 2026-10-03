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
import importlib.util as _ilu
import logging
import os
import sys
import time
import uuid
from functools import lru_cache
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Make sure backend/ can resolve its own siblings regardless of working dir
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SRC = os.path.join(os.path.dirname(_HERE), "src")

# Load the project .env once so provider keys are available automatically.
load_dotenv(os.path.join(_ROOT, ".env"), override=False)

# 1. Insert src/
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# 2. Insert backend/ (so it stays at index 0 and takes highest priority)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

if _ROOT not in sys.path:          # so `import prisma` (repo-root package) works on Railway
    sys.path.insert(0, _ROOT)

from data_ingestion import ingest_file, DataIngestionError
from reporting import generate_report
from llm_client import LLMClient
from prisma import (
    IngestError, PrismaConfig, build_ground_truth, compute_metrics, parse_insights,
    to_legacy_metrics, validate_claims,
)


def _load_local_module(module_name: str, filename: str):
    """Load a backend sibling module directly from file to avoid name collisions."""
    spec = _ilu.spec_from_file_location(module_name, os.path.join(_HERE, filename))
    module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)       # type: ignore[union-attr]
    return module


_csvl_mod = _load_local_module("prisma_csvl_engine", "csvl_engine.py")
run_csvl_pipeline = _csvl_mod.run_csvl_pipeline


def _load_prisma_config() -> PrismaConfig:
    """Single analysis config (Cohen thresholds, FDR alpha, ...) from config/config.yaml."""
    path = os.path.join(_ROOT, "config", "config.yaml")
    try:
        return PrismaConfig.from_yaml(path)
    except FileNotFoundError:
        return PrismaConfig()
    except Exception as exc:                      # a bad config must be loud, not silent
        raise RuntimeError(f"Invalid prisma section in {path}: {exc}") from exc


_PRISMA_CFG = _load_prisma_config()

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
    allow_origins=["*"],
    allow_credentials=False,
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
            groq_key=os.getenv("GROQ_API_KEY"),
            gemini_key=os.getenv("GEMINI_API_KEY"),
        )
    return _llm_client


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    session_id: str = Field(..., description="Session ID returned by /upload")
    model_provider: str = Field(default="ollama", description="ollama | groq | gemini")
    model_name: str | None = Field(default=None, description="Model name within the provider")
    use_csvl: bool = Field(default=True, description="Enable Closed-Loop Self-Validation")
    num_insights: int = Field(default=10, ge=1, le=30)
    groq_key: str | None = Field(default=None, description="Optional runtime Groq key")
    gemini_key: str | None = Field(default=None, description="Optional runtime Gemini key")


class HealthResponse(BaseModel):
    status: str
    version: str


class ProviderInfo(BaseModel):
    configured: bool
    source: str
    requires_api_key: bool
    env_var: str | None = None


class ProviderStatusResponse(BaseModel):
    providers: dict[str, ProviderInfo]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_model=HealthResponse, tags=["Health"])
async def root():
    return {"status": "ok", "version": app.version}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return {"status": "ok", "version": app.version}


@app.get("/providers/status", response_model=ProviderStatusResponse, tags=["Health"])
async def provider_status():
    """
    Return non-secret provider availability details for the frontend.
    Keys stay on the backend; the UI only learns whether a provider is configured.
    """
    return {
        "providers": {
            "ollama": {
                "configured": True,
                "source": "local_runtime",
                "requires_api_key": False,
                "env_var": None,
            },
            "groq": {
                "configured": bool(os.getenv("GROQ_API_KEY")),
                "source": "backend_env",
                "requires_api_key": True,
                "env_var": "GROQ_API_KEY",
            },
            "gemini": {
                "configured": bool(os.getenv("GEMINI_API_KEY")),
                "source": "backend_env",
                "requires_api_key": True,
                "env_var": "GEMINI_API_KEY",
            },
        }
    }


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
    if body.groq_key:
        llm.update_key("groq", body.groq_key)
    if body.gemini_key:
        llm.update_key("gemini", body.gemini_key)

    try:
        # 1. Statistical ground truth (v2: every tested pair, Cohen tiers, BH-FDR, no imputation)
        logger.info("[%s] Step 1 — statistical analysis", body.session_id)
        gt = build_ground_truth(df, _PRISMA_CFG)
        ground_truth = gt.to_legacy_dict()
        session["gt"] = gt
        session["ground_truth"] = ground_truth

        # 2. Prompt text from the SAME cleaned store the validator uses (G1)
        dataset_summary = _build_summary(gt)

        # 3. LLM generation (sync from executor so we don't block)
        logger.info("[%s] Step 2 — LLM generation (CSVL=%s)", body.session_id, body.use_csvl)

        if body.use_csvl:
            llm_output = await run_csvl_pipeline(
                ground_truth=gt,
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

        if not llm_output or not llm_output.strip():
            raise ValueError(
                f"The {body.model_provider} provider returned an empty response. "
                "Check the API key, selected model, or try disabling CSVL for a direct generation pass."
            )

        # 4. Parse
        logger.info("[%s] Step 3 — parsing insights", body.session_id)
        claims = parse_insights(llm_output, gt.schema, gt.cfg)
        if not claims:
            raise ValueError(
                "The model responded, but Prisma could not parse any numbered insights from it. "
                "Try disabling CSVL or switching providers/models."
            )

        # 5. Validate
        logger.info("[%s] Step 4 — validating claims", body.session_id)
        verdicts = validate_claims(claims, gt)
        validation_results = [v.to_legacy() for v in verdicts]

        # 6. Metrics + report (core metrics are fractions; legacy keys are percent)
        core_metrics = compute_metrics(verdicts)
        metrics = to_legacy_metrics(core_metrics)
        metrics["config_hash"] = gt.cfg.hash()
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

    except IngestError as exc:
        session["status"] = "error"
        raise HTTPException(status_code=422, detail=f"Dataset cannot be analysed: {exc}")
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

def _build_summary(gt: Any) -> str:
    """Prompt text = the full ranked ground-truth store (G1), not the top-5 correlations.

    Generated from the cleaned data the validator also uses, so the model and the
    checker can never disagree about e.g. Pima's zero-as-missing Insulin values."""
    return gt.to_prompt_block()


def _direct_prompt(summary: str) -> str:
    return (
        f"You are a data analyst.\n\n"
        f"Dataset summary:\n{summary}\n\n"
        "Generate exactly 10 concise, specific insights as a numbered list (1. ... 2. ...).\n"
        "Name the variables involved in each insight."
    )


def _serialize(obj: Any) -> Any:
    """Recursively make an object JSON-serialisable and replace NaNs with None."""
    import math
    # 1. Force python native scalar types (resolve np.int64, etc.)
    simple_obj = json.loads(json.dumps(obj, default=str))
    
    # 2. Walk and replace `nan` (which Starlette strict JSON rejects) with None
    def _sanitize(o: Any) -> Any:
        if isinstance(o, float) and math.isnan(o):
            return None
        elif isinstance(o, dict):
            return {k: _sanitize(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [_sanitize(v) for v in o]
        return o
        
    return _sanitize(simple_obj)
