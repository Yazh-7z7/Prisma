"""
reporting.py — Report Generation Service
Prisma | Production-Grade Backend

Produces:
  - JSON summary file
  - Structured metrics dict returned to the API caller
  - Markdown human-readable report
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("Prisma.Reporting")

# Six-label taxonomy (descriptive C4 claims are reported separately)
TAXONOMY_LABELS = [
    "VALID",
    "HALLUCINATION_RELATIONSHIP",
    "HALLUCINATION_DIRECTION",
    "HALLUCINATION_MAGNITUDE",
    "HALLUCINATION_VARIABLE",
    "UNVERIFIED",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_metrics(validation_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy-shaped metrics (dashboard contract). The arithmetic lives in
    ``prisma.metrics``; ``hallucination_rate``/``validity_score`` are PERCENT here
    and every metric also has an explicit ``*_frac`` / ``*_pct`` twin (fixes B7)."""
    from prisma.metrics import compute_metrics as _core, to_legacy_metrics
    return to_legacy_metrics(_core(validation_results))


def generate_report(
    validation_results: list[dict[str, Any]],
    metrics: dict[str, Any],
    dataset_name: str,
    model_name: str,
    output_dir: str = "results/reports",
) -> dict[str, Any]:
    """
    Write JSON + Markdown reports to *output_dir* and return their paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"{dataset_name}_{ts}"

    json_path = os.path.join(output_dir, f"{base}.json")
    md_path = os.path.join(output_dir, f"{base}.md")

    payload = {
        "metadata": {
            "dataset": dataset_name,
            "model": model_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": metrics,
        "validation_results": validation_results,
    }

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_markdown_report(payload))

    logger.info("Reports written → %s, %s", json_path, md_path)
    return {"json": json_path, "markdown": md_path}


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _empty_metrics() -> dict[str, Any]:
    return {
        "total_claims": 0,
        "valid_claims": 0,
        "verified_claims": 0,
        "hallucination_count": 0,
        "unverified_count": 0,
        "hallucination_rate": 0.0,
        "validity_score": 0.0,
        "taxonomy_distribution": {label: 0 for label in TAXONOMY_LABELS},
        "confidence_by_label": {label: 0.0 for label in TAXONOMY_LABELS},
        "avg_confidence": 0.0,
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    meta = payload["metadata"]
    m = payload["metrics"]
    results = payload["validation_results"]

    lines = [
        "# Prisma — Hallucination Analysis Report",
        "",
        f"**Dataset:** {meta['dataset']}  ",
        f"**Model:** {meta['model']}  ",
        f"**Generated:** {meta['generated_at']}",
        "",
        "## Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Claims | {m['total_claims']} |",
        f"| Valid | {m['valid_claims']} |",
        f"| Hallucinations | {m['hallucination_count']} |",
        f"| Unverified | {m['unverified_count']} |",
        f"| Hallucination Rate | {m['hallucination_rate']}% |",
        f"| Validity Score | {m['validity_score']}% |",
        f"| Avg Support Score (uncalibrated) | {m['avg_confidence']} |",
        f"| Hallucination Rate (fraction) | {m.get('hallucination_rate_frac')} |",
        "",
        "## Taxonomy Distribution",
        "",
    ]
    for label, count in m.get("taxonomy_distribution", {}).items():
        lines.append(f"- **{label}**: {count}")

    lines += ["", "## Claims", ""]
    for i, vr in enumerate(results, 1):
        claim_text = vr.get("claim", {}).get("original_text", "(no text)")
        status = vr.get("status", "?")
        reason = vr.get("reason", "")
        conf = vr.get("claim", {}).get("confidence_score", 0.5)
        lines.append(f"### {i}. {claim_text}")
        lines.append(f"**Status:** `{status}`  **Support:** {conf:.2f}")
        lines.append(f"**Reason:** {reason}")
        lines.append("")

    return "\n".join(lines)
