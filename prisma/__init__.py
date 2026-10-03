"""Prisma core: web-free statistical grounding + claim validation."""
from .config import DEFAULT_CONFIG, PrismaConfig
from .ground_truth import GroundTruth, build_ground_truth
from .ingest import IngestError, Prepared, prepare
from .metrics import compute_metrics, to_legacy_metrics
from .models import Claim, Verdict
from .parser import parse_insights
from .pipeline import AnalysisResult, analyze_dataframe, analyze_text
from .validator import validate_claim, validate_claims

__all__ = [
    "DEFAULT_CONFIG", "PrismaConfig", "GroundTruth", "build_ground_truth", "IngestError",
    "Prepared", "prepare", "compute_metrics", "to_legacy_metrics", "Claim", "Verdict",
    "parse_insights", "AnalysisResult", "analyze_dataframe", "analyze_text",
    "validate_claim", "validate_claims",
]
__version__ = "2.0.0-phase1"
