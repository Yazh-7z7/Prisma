"""
shared/types.py — Shared schema definitions (Python)
Used by both the FastAPI backend and any Python test utilities.
The TypeScript mirror is in frontend/src/types.ts.
"""

from __future__ import annotations

from typing import Any, Literal

# ── Hallucination taxonomy ────────────────────────────────────────────────────

ValidationStatus = Literal[
    "VALID",
    "HALLUCINATION_RELATIONSHIP",
    "HALLUCINATION_DIRECTION",
    "HALLUCINATION_MAGNITUDE",
    "HALLUCINATION_VARIABLE",
    "UNVERIFIED",
    "DESCRIPTIVE_INCORRECT",
]

TAXONOMY_LABELS: list[ValidationStatus] = [
    "VALID",
    "HALLUCINATION_RELATIONSHIP",
    "HALLUCINATION_DIRECTION",
    "HALLUCINATION_MAGNITUDE",
    "HALLUCINATION_VARIABLE",
    "UNVERIFIED",
]

# ── Claim ─────────────────────────────────────────────────────────────────────

class Claim:
    """Represents a single parsed insight claim."""

    def __init__(
        self,
        original_text: str,
        variables: list[str],
        relationship: str,
        direction: str,
        strength: str,
        confidence_score: float,
        type: str,
    ) -> None:
        self.original_text = original_text
        self.variables = variables
        self.relationship = relationship
        self.direction = direction
        self.strength = strength
        self.confidence_score = confidence_score
        self.type = type

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# ── ValidationResult ──────────────────────────────────────────────────────────

class ValidationResult:
    def __init__(
        self,
        claim: dict[str, Any],
        extracted_vars: list[str],
        status: ValidationStatus,
        reason: str,
        ground_truth: dict[str, Any] | None = None,
    ) -> None:
        self.claim = claim
        self.extracted_vars = extracted_vars
        self.status = status
        self.reason = reason
        self.ground_truth = ground_truth

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "extracted_vars": self.extracted_vars,
            "status": self.status,
            "reason": self.reason,
            "ground_truth": self.ground_truth,
        }
