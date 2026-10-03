"""
prisma.pipeline — the single web-free entry point (design decision 1).

FastAPI, the CLI runner and the tests all call these functions; none of them
re-implements parsing, validation or metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import DEFAULT_CONFIG, PrismaConfig
from .ground_truth import GroundTruth, build_ground_truth
from .metrics import compute_metrics
from .models import Claim, Verdict
from .parser import parse_insights
from .validator import validate_claims


@dataclass
class AnalysisResult:
    gt: GroundTruth
    claims: list[Claim]
    verdicts: list[Verdict]
    metrics: dict[str, Any]

    def to_record(self) -> dict[str, Any]:
        """JSON-serialisable record for a JSONL run log (Phase 2 runner)."""
        return {
            "config_hash": self.gt.cfg.hash(),
            "n_rows": self.gt.n_rows,
            "n_tests": self.gt.n_tests,
            "claims": [c.to_dict() for c in self.claims],
            "verdicts": [v.to_dict() for v in self.verdicts],
            "metrics": self.metrics,
        }


def analyze_text(llm_text: str, gt: GroundTruth) -> AnalysisResult:
    claims = parse_insights(llm_text, gt.schema, gt.cfg)
    verdicts = validate_claims(claims, gt)
    return AnalysisResult(gt=gt, claims=claims, verdicts=verdicts, metrics=compute_metrics(verdicts))


def analyze_dataframe(df: pd.DataFrame, llm_text: str,
                      cfg: PrismaConfig = DEFAULT_CONFIG) -> AnalysisResult:
    return analyze_text(llm_text, build_ground_truth(df, cfg))
