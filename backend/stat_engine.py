"""
backend/stat_engine.py — DEPRECATED SHIM.

The ground-truth engine lives in ``prisma.ground_truth`` (v2: every tested pair,
Cohen tiers, BH-FDR, no imputation). ``analyze`` is kept for old callers and
returns the legacy dict; new code should call ``prisma.build_ground_truth``
and keep the ``GroundTruth`` object.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from prisma import PrismaConfig, build_ground_truth  # noqa: E402


def analyze(df: pd.DataFrame, config: dict | None = None) -> dict[str, Any]:
    cfg = PrismaConfig.from_mapping((config or {}).get("prisma"))
    return build_ground_truth(df, cfg).to_legacy_dict()
