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

# Six-label taxonomy
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
    """
    Compute aggregated metrics from a list of validation result dicts.

    Returns a metrics dict consumed by both the API and the frontend.
    """
    total = len(validation_results)
    if total == 0:
        return _empty_metrics()

    counts: dict[str, int] = {label: 0 for label in TAXONOMY_LABELS}
    confidence_by_label: dict[str, list[float]] = {label: [] for label in TAXONOMY_LABELS}

    for vr in validation_results:
        status = vr.get("status", "UNVERIFIED")
        counts[status] = counts.get(status, 0) + 1
        conf: float = vr.get("claim", {}).get("confidence_score", 0.5)
        confidence_by_label.setdefault(status, []).append(float(conf))

    valid_count = counts.get("VALID", 0)
    hallucination_count = sum(
        counts.get(l, 0) for l in TAXONOMY_LABELS if l.startswith("HALLUCINATION")
    )

    return {
        "total_claims": total,
        "valid_claims": valid_count,
        "verified_claims": valid_count,
        "hallucination_count": hallucination_count,
        "unverified_count": counts.get("UNVERIFIED", 0),
        "hallucination_rate": round(hallucination_count / total * 100, 1),
        "validity_score": round(valid_count / total * 100, 1),
        "taxonomy_distribution": counts,
        "confidence_by_label": {
            label: round(sum(vals) / len(vals), 3) if vals else 0.0
            for label, vals in confidence_by_label.items()
        },
        "avg_confidence": round(
            sum(
                vr.get("claim", {}).get("confidence_score", 0.5)
                for vr in validation_results
            )
            / total,
            3,
        ),
    }


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
        f"| Avg Confidence | {m['avg_confidence']} |",
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
        lines.append(f"**Status:** `{status}`  **Confidence:** {conf:.2f}")
        lines.append(f"**Reason:** {reason}")
        lines.append("")

    return "\n".join(lines)
