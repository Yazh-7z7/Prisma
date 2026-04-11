"""
stat_engine.py — Statistical Ground Truth Engine
Prisma | Production-Grade Backend

Wraps and enhances src/statistical_engine.py with:
  - functools.lru_cache for repeated dataset hashes
  - async-friendly synchronous executor wrapper
  - Richer per-pair confidence formula: confidence = 0.6*(1-p) + 0.4*|r|
  - Unified output schema consumed by the FastAPI layer
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import os
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("Prisma.StatEngine")

# ---------------------------------------------------------------------------
# Config defaults (overridable via the config dict passed from main.py)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "statistics": {
        "significance_level": 0.05,
        "correlation_threshold": 0.3,
        "effect_size_thresholds": {"small": 0.2, "medium": 0.5, "large": 0.8},
    },
    "validation": {"fuzzy_match_threshold": 0.85},
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DataFrame cache: keyed by hash string to avoid lru_cache unhashable errors
# ---------------------------------------------------------------------------
_DF_CACHE: dict[str, pd.DataFrame] = {}


def analyze(df: pd.DataFrame, config: dict | None = None) -> dict[str, Any]:
    """
    Run the full statistical pipeline on *df* and return a ground-truth dict.

    The hash key ensures we never recompute identical frames.
    lru_cache cannot receive a DataFrame directly (not hashable), so we store
    it in a module-level dict keyed by its content hash.
    """
    cfg = config or DEFAULT_CONFIG
    cache_key = _df_hash(df)
    cfg_json = json.dumps(cfg, sort_keys=True)
    # Stash df so the lru_cache function can retrieve it by hash
    _DF_CACHE[cache_key] = df
    return _cached_analyze(cache_key, cfg_json)


# ---------------------------------------------------------------------------
# Cached core: receives only hashable primitives
# ---------------------------------------------------------------------------

@lru_cache(maxsize=16)
def _cached_analyze(cache_key: str, cfg_json: str) -> dict[str, Any]:
    """LRU-cached inner function.  Retrieves the DataFrame via the module dict."""
    df = _DF_CACHE[cache_key]
    cfg = json.loads(cfg_json)
    return _run_analysis(df, cfg)


# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------

def _run_analysis(df: pd.DataFrame, cfg: dict) -> dict[str, Any]:
    sig = cfg["statistics"]["significance_level"]
    thresholds = cfg["statistics"]["effect_size_thresholds"]

    result: dict[str, Any] = {
        "summary": _summary_stats(df),
        "correlations": _correlations(df, sig, thresholds),
        "group_differences": _group_differences(df, sig),
        "categorical_associations": _categorical_associations(df, sig, thresholds),
    }
    logger.info(
        "Statistical analysis done — %d correlations, %d group diffs, %d cat assocs",
        len(result["correlations"]),
        len(result["group_differences"]),
        len(result["categorical_associations"]),
    )
    return result


# ---------------------------------------------------------------------------
# Sub-routines
# ---------------------------------------------------------------------------

def _summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    stats_dict = df.describe(include="all").to_dict()
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    for col in cat_cols:
        if col not in stats_dict:
            stats_dict[col] = df[col].value_counts().to_dict()

    return {"stats": stats_dict, "dtypes": dtypes}


def _correlations(df: pd.DataFrame, sig: float, thresholds: dict) -> list[dict]:
    num_df = df.select_dtypes(include=[np.number])
    cols = num_df.columns
    n = len(cols)
    results = []

    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = cols[i], cols[j]
            tmp = num_df[[c1, c2]].dropna()
            if len(tmp) < 3:
                continue
            if tmp[c1].std() == 0 or tmp[c2].std() == 0:
                continue
            try:
                r_p, p_p = stats.pearsonr(tmp[c1], tmp[c2])
                r_s, p_s = stats.spearmanr(tmp[c1], tmp[c2])
            except Exception:
                continue

            is_sig = (p_p < sig) or (p_s < sig)
            if not is_sig:
                continue

            abs_r = max(abs(r_p), abs(r_s))
            strength = _strength(abs_r, thresholds)
            if strength == "negligible":
                continue

            confidence = round(
                min(max(0.6 * (1 - float(p_p)) + 0.4 * abs(float(r_p)), 0.01), 0.99), 3
            )

            results.append(
                {
                    "var1": c1,
                    "var2": c2,
                    "pearson": {"r": round(float(r_p), 4), "p": round(float(p_p), 6)},
                    "spearman": {"r": round(float(r_s), 4), "p": round(float(p_s), 6)},
                    "correlation": round(float(r_p), 4),
                    "p_value": round(float(p_p), 6),
                    "strength": strength,
                    "direction": "positive" if r_p > 0 else "negative",
                    "confidence": confidence,
                    "type": "correlation",
                }
            )
    return results


def _group_differences(df: pd.DataFrame, sig: float) -> list[dict]:
    num_cols = df.select_dtypes(include=[np.number]).columns
    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    results = []

    for num_col in num_cols:
        for cat_col in cat_cols:
            groups_data = []
            group_names = [g for g in df[cat_col].unique() if pd.notna(g)]

            if len(group_names) < 2:
                continue

            for g in group_names:
                vals = df.loc[df[cat_col] == g, num_col].dropna()
                if len(vals) > 1:
                    groups_data.append(vals)

            if len(groups_data) < 2:
                continue

            try:
                if len(groups_data) == 2:
                    stat, p_val = stats.ttest_ind(groups_data[0], groups_data[1], equal_var=False)
                    test = "t-test"
                else:
                    stat, p_val = stats.f_oneway(*groups_data)
                    test = "anova"
            except Exception:
                continue

            if p_val >= sig:
                continue

            means = {str(g): float(df.loc[df[cat_col] == g, num_col].mean()) for g in group_names if pd.notna(g)}
            highest = max(means, key=means.get)  # type: ignore[arg-type]
            lowest = min(means, key=means.get)  # type: ignore[arg-type]

            # Effect size (eta squared approximation via t-test Cohen's d proxy)
            n_total = sum(len(gd) for gd in groups_data)
            effect_size = abs(float(stat)) / (n_total ** 0.5)

            confidence = round(min(max(0.6 * (1 - float(p_val)), 0.01), 0.99), 3)

            results.append(
                {
                    "var1": cat_col,
                    "var2": num_col,
                    "variable": num_col,
                    "group_by": cat_col,
                    "test": test,
                    "p_value": round(float(p_val), 6),
                    "stat": round(float(stat), 4),
                    "effect_size": round(effect_size, 4),
                    "direction": f"{highest} > {lowest}",
                    "significant": True,
                    "group_means": means,
                    "confidence": confidence,
                    "type": "group_difference",
                }
            )
    return results


def _categorical_associations(df: pd.DataFrame, sig: float, thresholds: dict) -> list[dict]:
    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    n = len(cat_cols)
    results = []

    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = cat_cols[i], cat_cols[j]
            table = pd.crosstab(df[c1], df[c2])
            if table.shape[0] < 2 or table.shape[1] < 2:
                continue
            n_obs = int(table.sum().sum())
            if n_obs < 5:
                continue
            try:
                chi2, p, dof, _ = stats.chi2_contingency(table)
                if not np.isfinite(p):
                    continue
            except Exception:
                continue

            if p >= sig:
                continue

            min_dim = min(table.shape) - 1
            cv = float(np.sqrt(chi2 / (n_obs * min_dim))) if min_dim > 0 else 0.0
            strength = _strength(cv, thresholds)
            if strength == "negligible":
                continue

            confidence = round(min(max(0.6 * (1 - float(p)), 0.01), 0.99), 3)

            results.append(
                {
                    "var1": c1,
                    "var2": c2,
                    "test": "chi-square",
                    "p_value": round(float(p), 6),
                    "cramers_v": round(cv, 4),
                    "strength": strength,
                    "direction": "associated",
                    "confidence": confidence,
                    "type": "categorical_association",
                }
            )
    return results


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _strength(r: float, thresholds: dict) -> str:
    abs_r = abs(r)
    if abs_r >= thresholds.get("large", 0.8):
        return "strong"
    if abs_r >= thresholds.get("medium", 0.5):
        return "moderate"
    if abs_r >= thresholds.get("small", 0.2):
        return "weak"
    return "negligible"


def _df_hash(df: pd.DataFrame) -> str:
    """Stable hash of DataFrame content for caching."""
    try:
        raw = pd.util.hash_pandas_object(df, index=True).values.tobytes()
        return hashlib.md5(raw).hexdigest()
    except Exception:
        return hashlib.md5(df.to_csv().encode()).hexdigest()
