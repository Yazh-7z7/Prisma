"""
csvl_engine.py — Closed-Loop Self-Validating LLM (CSVL)

This module adds a 3-step reasoning loop on top of the existing LLMGenerator.
It does NOT modify any existing files. It is purely additive.

Pipeline:
  Step 1 → Initial insight generation  (same as before)
  Step 2 → Self-critique against stats  (NEW)
  Step 3 → Refined insight generation   (NEW)
  Step 4 → Existing validator runs on the refined output (UNCHANGED)

Usage (in app.py, replace the single generate_insights call):
  from src.csvl_engine import CSVLEngine
  csvl = CSVLEngine(llm_gen, logger)
  raw_response = csvl.generate_self_validated_insights(
      dataset_summary=summary_str,
      ground_truth=ground_truth,
      model_provider=st.session_state.provider,
      model_name=st.session_state.model_name
  )
"""

import logging
import json


class CSVLEngine:
    """
    Closed-Loop Self-Validating LLM engine.

    Wraps an existing LLMGenerator instance and adds a self-critique +
    refinement loop grounded in statistical ground truth before returning
    the final insight text to the rest of the pipeline.
    """

    def __init__(self, llm_generator, logger=None):
        """
        Parameters
        ----------
        llm_generator : LLMGenerator
            The already-initialised LLMGenerator from llm_generator.py.
            CSVL calls its provider.generate() directly so it can send
            custom prompts without changing generate_insights().
        logger : logging.Logger, optional
            Pass in the app logger or leave None for a default one.
        """
        self.llm_gen = llm_generator
        self.logger = logger or logging.getLogger("Prisma.CSVL")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate_self_validated_insights(
        self,
        dataset_summary: str,
        ground_truth: dict,
        model_provider: str = "ollama",
        model_name: str = None,
    ) -> str:
        """
        Run the 3-step CSVL pipeline and return final refined insight text.

        The return value is identical in format to what llm_generator.py's
        generate_insights() returns — a plain numbered-list string — so the
        rest of the pipeline (InsightParser → Validator) is completely
        unaffected.
        """
        # Compact stats summary so prompts don't balloon in size
        stats_summary = self._compact_stats(ground_truth)

        self.logger.info("[CSVL] Step 1 — Generating initial insights...")
        raw_insights = self._call_llm(
            self._prompt_generate(dataset_summary),
            model_provider,
            model_name,
        )
        if not raw_insights:
            self.logger.warning("[CSVL] Step 1 returned empty — falling back to direct generation.")
            return self._fallback(dataset_summary, model_provider, model_name)

        self.logger.info("[CSVL] Step 2 — Self-critique against statistical ground truth...")
        critique = self._call_llm(
            self._prompt_critique(raw_insights, stats_summary),
            model_provider,
            model_name,
        )
        if not critique:
            self.logger.warning("[CSVL] Step 2 returned empty — skipping refinement, using raw insights.")
            return raw_insights

        self.logger.info("[CSVL] Step 3 — Refining insights based on critique...")
        refined = self._call_llm(
            self._prompt_refine(raw_insights, critique, stats_summary),
            model_provider,
            model_name,
        )
        if not refined:
            self.logger.warning("[CSVL] Step 3 returned empty — using raw insights instead.")
            return raw_insights

        self.logger.info("[CSVL] Self-validation complete. Returning refined insights.")
        return refined

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _prompt_generate(self, dataset_summary: str) -> str:
        return f"""You are a data analyst.

Given this dataset summary:
{dataset_summary}

Generate exactly 10 insights about the most important relationships or patterns.
Focus on correlations, group differences, and trends visible in the data.

Format your response as a numbered list (1. ... 2. ... etc.).
Each insight should be one clear sentence that names the specific variables involved."""

    def _prompt_critique(self, raw_insights: str, stats_summary: str) -> str:
        return f"""You are a statistical auditor reviewing AI-generated insights.

Here are the generated insights:
{raw_insights}

Here is the verified statistical ground truth from the dataset:
{stats_summary}

For each numbered insight, evaluate:
1. Is the claim statistically supported by the ground truth above?
2. Is the direction of any relationship correct (positive/negative)?
3. Are there any unsupported or fabricated claims?

Output a numbered critique list matching the original insights.
For each, write: VALID or INVALID — then one sentence of explanation.
Do not generate new insights here, only evaluate the existing ones."""

    def _prompt_refine(self, raw_insights: str, critique: str, stats_summary: str) -> str:
        return f"""You are an AI analyst improving your own previous analysis.

Original insights:
{raw_insights}

Audit results from statistical review:
{critique}

Verified statistical ground truth:
{stats_summary}

Your task:
- Keep insights marked VALID unchanged.
- Fix insights marked INVALID so they accurately reflect the ground truth.
- If an insight cannot be fixed with available data, remove it and replace with a new valid one.
- Do not introduce any claims not supported by the ground truth above.

Output ONLY the final refined numbered list of insights (1. ... 2. ... etc.).
No preamble, no explanation — just the clean final list."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str, model_provider: str, model_name: str) -> str:
        """Call the underlying provider via LLMGenerator's provider dict."""
        try:
            provider = self.llm_gen.providers.get(model_provider)
            if not provider:
                self.logger.error(f"[CSVL] Provider '{model_provider}' not found.")
                return ""
            return provider.generate(prompt, model=model_name) or ""
        except Exception as e:
            self.logger.error(f"[CSVL] LLM call failed: {e}")
            return ""

    def _fallback(self, dataset_summary: str, model_provider: str, model_name: str) -> str:
        """
        If Step 1 fails entirely, fall back to the original single-call
        generate_insights() so the app never crashes.
        """
        self.logger.info("[CSVL] Using fallback: original single-call generation.")
        return self.llm_gen.generate_insights(
            dataset_summary=dataset_summary,
            model_provider=model_provider,
            model_name=model_name,
        )

    def _compact_stats(self, ground_truth: dict) -> str:
        """
        Produce a short, readable stats string from the ground_truth dict
        so prompts stay concise. Only includes the most informative fields.
        """
        try:
            parts = []

            # Correlations
            correlations = ground_truth.get("correlations", [])
            if correlations:
                parts.append("KEY CORRELATIONS:")
                for c in correlations[:8]:  # cap to avoid prompt bloat
                    parts.append(
                        f"  - {c.get('var1')} vs {c.get('var2')}: "
                        f"r={c.get('correlation', 0):.3f}, "
                        f"p={c.get('p_value', 1):.4f}"
                    )

            # Group differences
            group_diffs = ground_truth.get("group_differences", [])
            if group_diffs:
                parts.append("GROUP DIFFERENCES:")
                for g in group_diffs[:5]:
                    parts.append(
                        f"  - {g.get('variable')} by {g.get('group_by')}: "
                        f"effect_size={g.get('effect_size', 0):.3f}, "
                        f"significant={g.get('significant', False)}"
                    )

            # Summary stats (just mean/std for numeric cols)
            summary = ground_truth.get("summary", {}).get("stats", {})
            if summary:
                parts.append("SUMMARY STATS (mean / std):")
                for col, s in list(summary.items())[:6]:
                    mean = s.get("mean", "?")
                    std = s.get("std", "?")
                    if isinstance(mean, float):
                        parts.append(f"  - {col}: mean={mean:.2f}, std={std:.2f}")

            return "\n".join(parts) if parts else json.dumps(ground_truth, default=str)[:1500]

        except Exception:
            return json.dumps(ground_truth, default=str)[:1500]
