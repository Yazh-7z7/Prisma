"""
prisma.models — typed objects shared by every stage (design decision 2).

Claim types
    C1  correlation        numeric  x numeric
    C2  group difference   numeric  x (binary | categorical)
    C3  categorical assoc. (binary|categorical) x (binary|categorical)
    C4  descriptive        single-column statistic or dataset size

The hallucination taxonomy applies to C1-C3 only. C4 is reported separately.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# ----------------------------------------------------------------- taxonomy
VALID = "VALID"
H_RELATIONSHIP = "HALLUCINATION_RELATIONSHIP"
H_DIRECTION = "HALLUCINATION_DIRECTION"
H_MAGNITUDE = "HALLUCINATION_MAGNITUDE"
H_VARIABLE = "HALLUCINATION_VARIABLE"
UNVERIFIED = "UNVERIFIED"
DESC_INCORRECT = "DESCRIPTIVE_INCORRECT"      # C4 only; never counted in the taxonomy

TAXONOMY_LABELS: tuple[str, ...] = (
    VALID, H_RELATIONSHIP, H_DIRECTION, H_MAGNITUDE, H_VARIABLE, UNVERIFIED,
)
HALLUCINATION_LABELS: tuple[str, ...] = (
    H_RELATIONSHIP, H_DIRECTION, H_MAGNITUDE, H_VARIABLE,
)

# ------------------------------------------------------------ column kinds
NUMERIC = "numeric"
BINARY = "binary"
CATEGORICAL = "categorical"

TIER_NAMES: tuple[str, ...] = ("negligible", "weak", "moderate", "strong")
STRENGTH_TO_TIER = {"weak": 1, "moderate": 2, "strong": 3}


@dataclass
class ColumnInfo:
    name: str
    kind: str                                   # numeric | binary | categorical
    n_valid: int = 0
    n_missing: int = 0
    levels: list[Any] = field(default_factory=list)       # binary / categorical
    ordered: bool = False                       # numeric binary => levels have a natural order
    level_counts: dict[str, int] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)  # numeric & numeric-binary


@dataclass
class PairResult:
    """One *tested* pair. Every tested pair is stored, significant or not."""
    var1: str
    var2: str
    claim_type: str                             # C1 | C2 | C3
    test: str                                   # pearson | welch-t | anova | chi2 | fisher
    n: int
    effect_kind: str                            # r | d | eta2 | w
    effect: float                               # signed where a sign exists
    effect_abs: float                           # |effect| on its own scale
    effect_r: float                             # r-equivalent in [0,1] (for the support score)
    tier: int                                   # 0..3 (negligible..strong) on Cohen tiers
    p: float
    q: float = float("nan")                     # BH-FDR adjusted, filled after all tests
    supported: bool = False                     # q < alpha AND tier >= min_effect_tier
    direction: Optional[str] = None             # "positive" | "negative" | None (not defined)
    # C1 extras
    spearman_rho: Optional[float] = None
    spearman_p: Optional[float] = None
    # C2 extras (var1 = numeric column, var2 = grouping column for C2)
    num_var: Optional[str] = None
    cat_var: Optional[str] = None
    group_means: dict[str, float] = field(default_factory=dict)
    group_ns: dict[str, int] = field(default_factory=dict)
    higher_group: Optional[str] = None
    dropped_groups: list[str] = field(default_factory=list)
    eta2: Optional[float] = None
    # C3 extras
    cramers_v: Optional[float] = None
    low_expected_counts: bool = False

    @property
    def tier_name(self) -> str:
        return TIER_NAMES[self.tier]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tier_name"] = self.tier_name
        return d


@dataclass
class Mention:
    """A resolved reference to a column inside a clause (positions index the
    *normalised* clause text)."""
    column: str
    start: int
    end: int
    text: str
    level: Optional[str] = None                 # e.g. "ckd" for "patients with CKD"
    fuzzy: bool = False


@dataclass
class Ghost:
    phrase: str
    evidence: str                               # "identifier" | "slot"


@dataclass
class Claim:
    text: str                                   # original item text (for display)
    clause: str                                 # normalised clause this claim came from
    item_index: int
    clause_index: int = 0
    split_index: int = 0                        # >0 when a compound clause was split
    kind: str = "relational"                    # relational | descriptive | non_relational
    type: Optional[str] = None                  # C1 | C2 | C3 | C4 | None
    mentions: list[Mention] = field(default_factory=list)
    vars: list[str] = field(default_factory=list)          # unique, in MENTION order (B1)
    direction: str = "unknown"                  # positive | negative | unknown
    strength: str = "unknown"                   # strong | moderate | weak | unknown
    asserts_null: bool = False                  # "no significant relationship ..."
    claims_significance: bool = False           # said "significant" (NOT a strength; B6)
    level: Optional[str] = None                 # group level named in a C2 claim
    level_direction: Optional[str] = None       # "higher" | "lower" within that level
    value: dict[str, Any] = field(default_factory=dict)   # numbers quoted: r, p, n, d, numbers[]
    stat_key: Optional[str] = None              # C4: mean|median|min|max|std|range|n_rows|missing
    ghosts: list[Ghost] = field(default_factory=list)
    ambiguous: Optional[str] = None             # reason, if the claim could not be attributed
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_legacy(self, support: Optional[float] = None) -> dict[str, Any]:
        """Shape consumed by the existing Next.js frontend."""
        rel = {"C1": "correlation", "C2": "group_difference",
               "C3": "categorical_association", "C4": "descriptive"}.get(self.type or "", "unknown")
        return {
            "original_text": self.text,
            "clause": self.clause,
            "variables": list(self.vars),
            "relationship": rel,
            "type": rel,
            "claim_type": self.type,
            "item_index": self.item_index,
            "direction": self.direction,
            "strength": self.strength,
            "asserts_null": self.asserts_null,
            "confidence_score": float(support) if support is not None else 0.0,
            "support_score": support,
        }


@dataclass
class Verdict:
    claim: Claim
    status: str
    reason: str
    truth: Optional[dict[str, Any]] = None
    support: Optional[float] = None             # statistical support score (uncalibrated)
    checks: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None                 # set only if the validator itself failed

    @property
    def is_relational(self) -> bool:
        return self.claim.type in ("C1", "C2", "C3")

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(), "status": self.status, "reason": self.reason,
            "truth": self.truth, "support": self.support, "checks": self.checks,
            "error": self.error,
        }

    def to_legacy(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_legacy(self.support),
            "extracted_vars": list(self.claim.vars),
            "status": self.status,
            "reason": self.reason,
            "ground_truth": self.truth,
            "checks": self.checks,
        }
