"""
parser.py — Insight Parser (FastAPI backend edition)
Prisma | Production-Grade Backend

Enhances src/insight_parser.py with:
  - Structured Pydantic-compatible output dicts
  - Bullet-list and markdown heading extraction (not just numbered lists)
  - Richer direction / strength keyword detection
  - Clean API used by api_server.py
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("Prisma.Parser")

# ---------------------------------------------------------------------------
# Direction / strength keyword maps
# ---------------------------------------------------------------------------
_POSITIVE_WORDS = frozenset(
    ["positive", "increases", "rises", "grows", "higher", "more", "upward", "directly"]
)
_NEGATIVE_WORDS = frozenset(
    ["negative", "decreases", "falls", "drops", "lower", "less", "downward", "inversely"]
)
_STRENGTH_MAP = {
    "strong": frozenset(["strong", "significant", "robust", "substantial", "highly"]),
    "moderate": frozenset(["moderate", "moderate", "medium", "somewhat"]),
    "weak": frozenset(["weak", "small", "slight", "marginal", "minor"]),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_insights(llm_output: str) -> list[dict[str, Any]]:
    """
    Parse LLM output into a list of structured claim dicts.

    Each claim contains:
      original_text   : str
      variables       : list[str]   (empty — filled later by validator)
      relationship    : str
      direction       : 'positive' | 'negative' | 'unknown'
      strength        : 'strong' | 'moderate' | 'weak' | 'unknown'
      confidence_score: float       (keyword-based init; overwritten by validator)
      type            : str
    """
    if not llm_output or not isinstance(llm_output, str):
        logger.warning("Empty or non-string LLM output supplied to parser.")
        return []

    lines = _extract_lines(llm_output)
    insights: list[dict[str, Any]] = []

    for line in lines:
        claim = _build_claim(line)
        if claim:
            insights.append(claim)

    logger.info("Parser extracted %d claims.", len(insights))
    return insights


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_lines(text: str) -> list[str]:
    """Extract non-empty, meaningful lines from LLM output."""
    lines: list[str] = []
    for raw in text.split("\n"):
        stripped = raw.strip()
        if not stripped:
            continue
        # Numbered list item:  "1. ..." or "1) ..."
        m = re.match(r"^\d+[.)]\s+(.*)", stripped)
        if m:
            lines.append(m.group(1).strip())
            continue
        # Bullet list item:  "- ..." or "* ..."
        m2 = re.match(r"^[-*•]\s+(.*)", stripped)
        if m2:
            lines.append(m2.group(1).strip())
            continue
        # Bold markdown heading: "**Title**"
        m3 = re.match(r"^\*\*(.+?)\*\*", stripped)
        if m3:
            lines.append(m3.group(1).strip())
            continue
    return lines


def _build_claim(text: str) -> dict[str, Any] | None:
    if len(text) < 10:          # Skip trivially short fragments
        return None

    lower = text.lower()
    tokens = set(lower.split())

    # Direction
    if tokens & _POSITIVE_WORDS:
        direction = "positive"
    elif tokens & _NEGATIVE_WORDS:
        direction = "negative"
    else:
        direction = "unknown"

    # Strength
    strength = "unknown"
    conf = 0.5
    for level, keywords in _STRENGTH_MAP.items():
        if tokens & keywords:
            strength = level
            conf = {"strong": 0.8, "moderate": 0.6, "weak": 0.4}[level]
            break

    return {
        "original_text": text,
        "variables": [],
        "relationship": "correlation",
        "direction": direction,
        "strength": strength,
        "confidence_score": conf,
        "type": "correlation",
    }
