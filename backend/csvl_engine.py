"""
csvl_engine.py — Closed-Loop Self-Validating LLM (CSVL) — Backend Edition
Prisma | Production-Grade Backend

Async-native version of src/csvl_engine.py.
Runs Generate → Critique → Refine in a single async call so FastAPI
can await it without blocking the event loop.

Provider abstraction matches llm_generator.py in src/.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("Prisma.CSVLEngine")


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------

async def run_csvl_pipeline(
    ground_truth: dict[str, Any],
    dataset_summary: str,
    llm_client: Any,             # compatible with backend/llm_client.py
    model_provider: str = "ollama",
    model_name: str | None = None,
) -> str:
    """
    Async closed-loop pipeline:
      Step 1 → Generate initial insights
      Step 2 → Critique against statistical ground truth
      Step 3 → Refine / remove hallucinated claims

    Returns the final refined insight text (numbered list, same format as
    a plain generate call) for downstream parsing.
    """
    stats_block = _compact_stats(ground_truth)

    logger.info("[CSVL] Step 1 — generating initial insights …")
    raw = await _llm(
        _prompt_generate(dataset_summary),
        llm_client, model_provider, model_name,
    )
    if not raw:
        logger.warning("[CSVL] Step 1 empty — returning empty.")
        return ""

    logger.info("[CSVL] Step 2 — self-critique against ground truth …")
    critique = await _llm(
        _prompt_critique(raw, stats_block),
        llm_client, model_provider, model_name,
    )
    if not critique:
        logger.warning("[CSVL] Step 2 empty — returning raw insights.")
        return raw

    logger.info("[CSVL] Step 3 — refining hallucinated claims …")
    refined = await _llm(
        _prompt_refine(raw, critique, stats_block),
        llm_client, model_provider, model_name,
    )
    if not refined:
        logger.warning("[CSVL] Step 3 empty — returning raw insights.")
        return raw

    logger.info("[CSVL] Pipeline complete.")
    return refined


# ---------------------------------------------------------------------------
# Non-async wrapper for Streamlit / sync callers
# ---------------------------------------------------------------------------

def run_csvl_pipeline_sync(
    ground_truth: dict[str, Any],
    dataset_summary: str,
    llm_client: Any,
    model_provider: str = "ollama",
    model_name: str | None = None,
) -> str:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            run_csvl_pipeline(
                ground_truth, dataset_summary,
                llm_client, model_provider, model_name,
            )
        )
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _prompt_generate(summary: str) -> str:
    return f"""You are a senior data analyst.

Dataset summary:
{summary}

Generate exactly 10 insights about the most important relationships or patterns.
Focus on correlations, group differences, and trends visible in the data.

Format: numbered list (1. ... 2. ... etc.).
Each insight = one clear sentence naming the specific variables involved."""


def _prompt_critique(raw: str, stats: str) -> str:
    return f"""You are a statistical auditor.

Generated insights:
{raw}

Verified statistical ground truth:
{stats}

For each insight evaluate:
1. Is it statistically supported?
2. Is the direction (positive/negative) correct?
3. Are there fabricated variable names?

Output a numbered critique list:
VALID or INVALID — one-sentence reason.
Do NOT generate new insights here."""


def _prompt_refine(raw: str, critique: str, stats: str) -> str:
    return f"""You are an AI analyst improving your own earlier analysis.

Original insights:
{raw}

Audit results:
{critique}

Verified statistical ground truth:
{stats}

Instructions:
- Keep VALID insights unchanged.
- Fix INVALID insights to accurately reflect the ground truth.
- If an insight cannot be fixed, remove it and add a supported one.
- Do NOT introduce claims not in the ground truth.

Output ONLY the final refined numbered list. No preamble."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _llm(
    prompt: str,
    client: Any,
    provider: str,
    model: str | None,
) -> str:
    """Dispatch to the async-aware llm_client wrapper."""
    try:
        # Run in executor so blocking SDK calls don't stall the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: client.generate(prompt, provider=provider, model=model),
        )
    except Exception as exc:
        logger.error("[CSVL] LLM call failed: %s", exc)
        return ""


def _compact_stats(ground_truth: dict[str, Any]) -> str:
    """Produce a short stats string for prompt injection."""
    try:
        parts: list[str] = []

        correlations = ground_truth.get("correlations", [])
        if correlations:
            parts.append("KEY CORRELATIONS:")
            for c in correlations[:8]:
                parts.append(
                    f"  - {c.get('var1')} vs {c.get('var2')}: "
                    f"r={c.get('pearson', {}).get('r', c.get('correlation', 0)):.3f}, "
                    f"p={c.get('pearson', {}).get('p', c.get('p_value', 1)):.4f}"
                )

        group_diffs = ground_truth.get("group_differences", [])
        if group_diffs:
            parts.append("GROUP DIFFERENCES:")
            for g in group_diffs[:5]:
                parts.append(
                    f"  - {g.get('variable', g.get('var2'))} by {g.get('group_by', g.get('var1'))}: "
                    f"effect_size={g.get('effect_size', 0):.3f}, "
                    f"significant={g.get('significant', True)}"
                )

        summary = ground_truth.get("summary", {}).get("stats", {})
        if summary:
            parts.append("SUMMARY STATS (mean / std):")
            for col, s in list(summary.items())[:6]:
                mean = s.get("mean", "?") if isinstance(s, dict) else "?"
                std = s.get("std", "?") if isinstance(s, dict) else "?"
                if isinstance(mean, float):
                    parts.append(f"  - {col}: mean={mean:.2f}, std={std:.2f}")

        return "\n".join(parts) if parts else json.dumps(ground_truth, default=str)[:1500]
    except Exception:
        return json.dumps(ground_truth, default=str)[:1500]
