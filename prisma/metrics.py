"""
prisma.metrics — aggregation with EXPLICIT units (fixes B7).

Inside the core every rate is a FRACTION in [0, 1].  Percentages exist only in
``to_legacy_metrics`` (the Next.js dashboard contract) and are always accompanied
by an unambiguous ``*_frac`` / ``*_pct`` pair.  Paper tables must be built from the
``*_frac`` keys of logged runs, never from the legacy ``hallucination_rate``.

Denominators
  taxonomy claims  = every atomic claim that is NOT descriptive (C4)
  hallucination_rate            = hallucinations / taxonomy claims
  hallucination_rate_verifiable = hallucinations / (hallucinations + VALID)   (excludes UNVERIFIED)
  Descriptive (C4) claims are reported separately and never enter the taxonomy.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .models import (
    DESC_INCORRECT, HALLUCINATION_LABELS, TAXONOMY_LABELS, UNVERIFIED, VALID, Verdict,
)


def _norm_records(items: Iterable[Any]) -> list[tuple[str, str | None, float | None, int | None]]:
    recs = []
    for v in items:
        if isinstance(v, Verdict):
            recs.append((v.status, v.claim.type, v.support, v.claim.item_index))
        else:  # legacy dict
            c = v.get("claim", {}) or {}
            recs.append((v.get("status", UNVERIFIED), c.get("claim_type"),
                         c.get("support_score"), c.get("item_index")))
    return recs


def _frac(a: int, b: int) -> float:
    return a / b if b else 0.0


def compute_metrics(verdicts: Iterable[Any]) -> dict[str, Any]:
    recs = _norm_records(verdicts)
    tax = [r for r in recs if r[1] != "C4"]
    desc = [r for r in recs if r[1] == "C4"]

    counts = Counter({lbl: 0 for lbl in TAXONOMY_LABELS})
    counts.update(r[0] for r in tax)
    n_tax = len(tax)
    n_h = sum(counts[l] for l in HALLUCINATION_LABELS)
    n_valid = counts[VALID]

    support_all = [r[2] for r in tax if r[2] is not None]
    by_label: dict[str, list[float]] = {l: [] for l in TAXONOMY_LABELS}
    for st, _t, sup, _i in tax:
        if sup is not None:
            by_label.setdefault(st, []).append(sup)

    d_counts = Counter(r[0] for r in desc)
    return {
        "n_claims": len(recs),
        "n_taxonomy_claims": n_tax,
        "n_descriptive_claims": len(desc),
        "n_items": len({r[3] for r in recs if r[3] is not None}),
        "counts": dict(counts),
        "n_valid": n_valid,
        "n_hallucinations": n_h,
        "n_unverified": counts[UNVERIFIED],
        "hallucination_rate": _frac(n_h, n_tax),
        "hallucination_rate_verifiable": _frac(n_h, n_h + n_valid),
        "valid_rate": _frac(n_valid, n_tax),
        "unverified_rate": _frac(counts[UNVERIFIED], n_tax),
        "ghost_rate": _frac(counts["HALLUCINATION_VARIABLE"], n_tax),
        "category_rates": {l: _frac(counts[l], n_tax) for l in HALLUCINATION_LABELS},
        "yield_valid": n_valid,
        "avg_support": (sum(support_all) / len(support_all)) if support_all else None,
        "n_with_support": len(support_all),
        "support_by_label": {l: (sum(v) / len(v) if v else None) for l, v in by_label.items()},
        "descriptive": {
            "n": len(desc), "valid": d_counts[VALID], "incorrect": d_counts[DESC_INCORRECT],
            "unverified": d_counts[UNVERIFIED],
            "incorrect_rate": _frac(d_counts[DESC_INCORRECT], len(desc)),
        },
        "units": "all *_rate values are fractions in [0, 1]",
    }


def to_legacy_metrics(m: dict[str, Any]) -> dict[str, Any]:
    """Shape the Next.js dashboard expects.  ``hallucination_rate`` and
    ``validity_score`` are PERCENT here (legacy contract); explicit pairs are included."""
    n = m["n_taxonomy_claims"]
    return {
        "total_claims": m["n_claims"],
        "valid_claims": m["n_valid"],
        "verified_claims": m["n_valid"],
        "hallucination_count": m["n_hallucinations"],
        "unverified_count": m["n_unverified"],
        "hallucination_rate": round(m["hallucination_rate"] * 100, 1),     # PERCENT (legacy)
        "validity_score": round(m["valid_rate"] * 100, 1),                 # PERCENT (legacy)
        "hallucination_rate_pct": round(m["hallucination_rate"] * 100, 2),
        "hallucination_rate_frac": round(m["hallucination_rate"], 4),
        "hallucination_rate_verifiable_frac": round(m["hallucination_rate_verifiable"], 4),
        "taxonomy_distribution": dict(m["counts"]),
        "confidence_by_label": {k: (round(v, 3) if v is not None else 0.0)
                                for k, v in m["support_by_label"].items()},
        "avg_confidence": round(m["avg_support"], 3) if m["avg_support"] is not None else 0.0,
        "avg_support": round(m["avg_support"], 3) if m["avg_support"] is not None else None,
        "descriptive": m["descriptive"],
        "n_taxonomy_claims": n,
        "units": {"hallucination_rate": "percent", "validity_score": "percent",
                  "*_frac": "fraction in [0,1]", "*_pct": "percent"},
    }
