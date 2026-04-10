"""
validator.py — Hallucination Validator (FastAPI backend edition)
Prisma | Production-Grade Backend

Full five-category taxonomy:
  VALID
  HALLUCINATION_RELATIONSHIP
  HALLUCINATION_DIRECTION
  HALLUCINATION_MAGNITUDE
  HALLUCINATION_VARIABLE
  UNVERIFIED

Confidence formula: confidence = 0.6*(1-p) + 0.4*|r|
(clipped to [0.01, 0.99])

Delegates ghost-variable detection and fuzzy matching to helpers.
Reuses patterns from src/validator.py but is independent of Streamlit.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("Prisma.Validator")

try:
    from fuzzywuzzy import fuzz
    _HAS_FUZZ = True
except ImportError:
    _HAS_FUZZ = False
    logger.warning("fuzzywuzzy not installed — falling back to substring matching.")

# Fuzzy threshold (0-100 scale)
FUZZY_THRESHOLD = 75

# Stopwords that should never be treated as column names
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "this", "there", "in", "a", "an", "it", "if", "is", "as",
        "for", "with", "that", "these", "those", "when", "between", "and",
        "or", "of", "to", "from", "by", "on", "at", "are", "has", "have",
        "higher", "lower", "positive", "negative", "strong", "weak", "no",
        "moderate", "significant", "relationship", "correlation", "dataset",
        "pearson", "spearman", "kendall", "chi", "anova", "ttest",
        "cramer", "cramers", "fisher", "shapiro", "wilcoxon", "mann",
        "whitney", "kruskal", "wallis", "bonferroni", "tukey",
        "mean", "median", "mode", "range", "distribution", "variance",
        "standard", "deviation", "outlier", "trend", "pattern", "analysis",
        "value", "values", "feature", "features", "variable", "variables",
        "increase", "decrease", "associated", "suggests", "indicates",
        "patients", "people", "individuals", "group", "groups", "data",
        "table", "column", "row", "sample", "population", "study",
        "effect", "size", "score", "rate", "risk", "index", "level",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_claims(
    claims: list[dict[str, Any]],
    ground_truth: dict[str, Any],
    df_columns: list[str],
) -> list[dict[str, Any]]:
    """
    Validate each claim and return augmented result dicts.

    Each result contains:
      claim         : original claim dict (possibly with updated confidence_score)
      extracted_vars: list[str]
      status        : taxonomy label
      reason        : human-readable explanation
      ground_truth  : the matched truth entry (if found)
    """
    results = []
    for claim in claims:
        results.append(_validate_one(claim, ground_truth, list(df_columns)))
    logger.info(
        "Validated %d claims. Distribution: %s",
        len(results),
        _distribution(results),
    )
    return results


# ---------------------------------------------------------------------------
# Single-claim validation
# ---------------------------------------------------------------------------

def _validate_one(
    claim: dict[str, Any],
    ground_truth: dict[str, Any],
    df_columns: list[str],
) -> dict[str, Any]:
    text = claim.get("original_text", "")
    base = {"claim": claim, "extracted_vars": [], "status": "UNVERIFIED", "reason": ""}

    if not text:
        base["reason"] = "Empty claim text."
        return base

    # --- Ghost-variable check (HALLUCINATION_VARIABLE) ---
    ghosts = _detect_ghosts(text, df_columns)
    if ghosts:
        base["extracted_vars"] = _extract_vars(text, df_columns)
        base["status"] = "HALLUCINATION_VARIABLE"
        base["reason"] = f"Non-existent variable(s) referenced: {', '.join(ghosts)}"
        return base

    # --- Extract real variables ---
    matched_vars = _extract_vars(text, df_columns)
    base["extracted_vars"] = matched_vars

    # --- Metadata / single-variable claims ---
    if "sample size" in text.lower() or "n=" in text.lower():
        return _validate_metadata(text, ground_truth, base)

    if len(matched_vars) == 1:
        return _validate_descriptive(text, matched_vars[0], ground_truth, base)

    if len(matched_vars) < 2:
        base["reason"] = "Too few variables identified in claim."
        return base

    var1, var2 = matched_vars[0], matched_vars[1]

    # --- Look up ground truth ---
    truth = _find_truth(var1, var2, ground_truth)
    if truth is None:
        base["status"] = "HALLUCINATION_RELATIONSHIP"
        base["reason"] = f"No statistical relationship found between '{var1}' and '{var2}'."
        return base

    # Recompute confidence from real stats
    confidence = _compute_confidence(truth)
    updated_claim = dict(claim)
    updated_claim["confidence_score"] = confidence
    base["claim"] = updated_claim

    # --- Direction check ---
    claimed_dir = claim.get("direction", "unknown")
    true_dir = truth.get("direction", "unknown")
    if claimed_dir not in ("unknown", true_dir):
        base["status"] = "HALLUCINATION_DIRECTION"
        base["reason"] = (
            f"Claimed direction '{claimed_dir}' contradicts actual '{true_dir}'."
        )
        base["ground_truth"] = truth
        return base

    # --- Magnitude check ---
    mag_err = _check_magnitude(claim, truth)
    if mag_err:
        base["status"] = "HALLUCINATION_MAGNITUDE"
        base["reason"] = mag_err
        base["ground_truth"] = truth
        return base

    base["status"] = "VALID"
    base["reason"] = "Claim is consistent with statistical ground truth."
    base["ground_truth"] = truth
    return base


# ---------------------------------------------------------------------------
# Helpers — confidence
# ---------------------------------------------------------------------------

def _compute_confidence(truth: dict[str, Any]) -> float:
    p_val: float | None = None
    r_val: float | None = None

    pearson = truth.get("pearson")
    if isinstance(pearson, dict):
        p_val = pearson.get("p")
        r_val = pearson.get("r")

    if p_val is None:
        p_val = truth.get("p_value")
    if r_val is None:
        r_val = truth.get("correlation") or truth.get("cramers_v") or truth.get("effect_size")

    try:
        p_sig = 1.0 - max(0.0, min(1.0, float(p_val))) if p_val is not None else None
        r_sig = min(abs(float(r_val)), 1.0) if r_val is not None else None

        if p_sig is not None and r_sig is not None:
            score = 0.6 * p_sig + 0.4 * r_sig
        elif p_sig is not None:
            score = p_sig
        elif r_sig is not None:
            score = r_sig
        else:
            return 0.5
        return round(max(0.01, min(0.99, score)), 3)
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# Helpers — variable extraction & ghost detection
# ---------------------------------------------------------------------------

def _extract_vars(text: str, columns: list[str]) -> list[str]:
    found: list[str] = []
    text_lower = text.lower()
    for col in columns:
        if col.lower() in text_lower:
            found.append(col)
            continue
        if _HAS_FUZZ:
            ratio = fuzz.partial_ratio(col.lower(), text_lower)
            if ratio >= FUZZY_THRESHOLD and col not in found:
                found.append(col)
    return found


def _detect_ghosts(text: str, columns: list[str]) -> list[str]:
    col_lower = {c.lower() for c in columns}
    col_subwords: set[str] = set()
    for col in columns:
        col_subwords.update(re.findall(r"[a-z]+", col.lower()))

    candidates = re.findall(r"\b[A-Z][a-zA-Z]+\b", text)
    ghosts: list[str] = []

    for cand in candidates:
        cl = cand.lower()
        if cl in _STOPWORDS:
            continue
        if cl in col_lower or cl in col_subwords:
            continue
        if _HAS_FUZZ:
            best = max((fuzz.ratio(cl, c.lower()) for c in columns), default=0)
            if best >= 70:
                continue
        ghosts.append(cand)

    return ghosts


def _find_truth(
    var1: str, var2: str, ground_truth: dict[str, Any]
) -> dict[str, Any] | None:
    for key in ("correlations", "group_differences", "categorical_associations"):
        for entry in ground_truth.get(key, []):
            v1, v2 = entry.get("var1"), entry.get("var2")
            if (v1 == var1 and v2 == var2) or (v1 == var2 and v2 == var1):
                return entry
    return None


def _check_magnitude(claim: dict[str, Any], truth: dict[str, Any]) -> str | None:
    claimed = claim.get("strength", "unknown")
    if claimed == "unknown":
        return None

    r = truth.get("correlation") or truth.get("cramers_v")
    if r is None:
        return None

    abs_r = abs(float(r))
    actual = "strong" if abs_r >= 0.6 else "moderate" if abs_r >= 0.3 else "weak"

    bad = (
        (claimed == "strong" and actual == "weak")
        or (claimed == "weak" and actual == "strong")
    )
    if bad:
        return (
            f"Claimed '{claimed}' but actual |r|={abs_r:.3f} indicates '{actual}'."
        )
    return None


# ---------------------------------------------------------------------------
# Helpers — metadata / descriptive
# ---------------------------------------------------------------------------

def _validate_metadata(
    text: str, ground_truth: dict[str, Any], base: dict[str, Any]
) -> dict[str, Any]:
    numbers = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", text) if x]
    summary = ground_truth.get("summary", {}).get("stats", {})
    if summary:
        first_col = next(iter(summary))
        count = summary[first_col].get("count", 0) if isinstance(summary[first_col], dict) else 0
        for n in numbers:
            if abs(n - count) < 10:
                base["status"] = "VALID"
                base["reason"] = f"Sample size ~{int(n)} verified."
                return base
    base["status"] = "UNVERIFIED"
    base["reason"] = "Could not verify sample size."
    return base


def _validate_descriptive(
    text: str, variable: str, ground_truth: dict[str, Any], base: dict[str, Any]
) -> dict[str, Any]:
    stat = ground_truth.get("summary", {}).get("stats", {}).get(variable, {})
    if not isinstance(stat, dict):
        return base

    lower = text.lower()
    numbers = []
    for x in re.findall(r"[-+]?\d*\.?\d+", text):
        try:
            numbers.append(float(x))
        except ValueError:
            pass

    checks = [
        (["mean", "average"], "mean"),
        (["median", "50%", "middle"], "50%"),
        (["minimum", "min"], "min"),
        (["maximum", "max"], "max"),
        (["deviation", "std"], "std"),
    ]
    for keywords, stat_key in checks:
        if any(kw in lower for kw in keywords):
            ref = stat.get(stat_key)
            if ref is not None:
                for n in numbers:
                    if abs(n - float(ref)) / (abs(float(ref)) + 1e-9) < 0.1:
                        base["status"] = "VALID"
                        base["reason"] = f"{stat_key} for {variable} verified (~{n})."
                        return base
    return base


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _distribution(results: list[dict[str, Any]]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in results:
        s = r.get("status", "UNKNOWN")
        dist[s] = dist.get(s, 0) + 1
    return dist
