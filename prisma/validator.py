"""
prisma.validator — typed validator v2 (fixes B1, B4; decisions 3, 4, 6).

Verdict order for a relational claim (C1-C3):
  1. ghost variable(s) named             -> HALLUCINATION_VARIABLE
  2. ambiguous / <2 resolvable columns   -> UNVERIFIED
  3. pair not testable                   -> UNVERIFIED   (never "null")
  4. pair tested and NOT supported       -> HALLUCINATION_RELATIONSHIP (or VALID for a null claim)
  5. pair supported:
       null claim                        -> HALLUCINATION_RELATIONSHIP
       direction contradicts (only where a direction exists)   -> HALLUCINATION_DIRECTION
       magnitude >= magnitude_tier_gap tiers off / quoted r far off -> HALLUCINATION_MAGNITUDE
       else                              -> VALID

``supported`` = BH-FDR q < alpha AND effect tier >= min_effect_tier (one config).
Direction is only checked where it exists: sign of r (C1), sign of d for an ORDERED
binary or a named group level (C2), sign of phi for two ordered binaries (C3).
Multi-level / unordered / chi-square claims are never penalised for "direction".

A validator exception never propagates: the claim becomes UNVERIFIED with ``error`` set.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .config import PrismaConfig
from .ground_truth import GroundTruth
from .models import (
    DESC_INCORRECT, H_DIRECTION, H_MAGNITUDE, H_RELATIONSHIP, H_VARIABLE,
    STRENGTH_TO_TIER, TIER_NAMES, UNVERIFIED, VALID, Claim, PairResult, Verdict,
)
from .support import support_score

logger = logging.getLogger("Prisma.Validator")


def validate_claims(claims: list[Claim], gt: GroundTruth) -> list[Verdict]:
    out = [validate_claim(c, gt) for c in claims]
    logger.info("Validated %d claims.", len(out))
    return out


def validate_claim(claim: Claim, gt: GroundTruth) -> Verdict:
    try:
        return _validate(claim, gt)
    except Exception as exc:                       # isolation: one bad claim must not kill a run
        logger.exception("Validator failed on claim %r", claim.text[:80])
        return Verdict(claim=claim, status=UNVERIFIED,
                       reason=f"Internal validator error: {exc}", error=repr(exc))


# -------------------------------------------------------------------------
def _validate(claim: Claim, gt: GroundTruth) -> Verdict:
    cfg = gt.cfg
    if claim.ghosts:
        names = ", ".join(f"'{g.phrase}'" for g in claim.ghosts)
        ev = sorted({g.evidence for g in claim.ghosts})
        return Verdict(claim, H_VARIABLE,
                       f"Refers to variable(s) not in the dataset: {names}.",
                       checks={"ghost_evidence": ev})

    if claim.type == "C4":
        return _validate_descriptive(claim, gt)

    if claim.ambiguous:
        return Verdict(claim, UNVERIFIED, claim.ambiguous)
    if len(claim.vars) < 2 or claim.type is None:
        why = "; ".join(claim.notes) if claim.notes else "fewer than two columns identified"
        return Verdict(claim, UNVERIFIED, f"Cannot verify: {why}.")

    var1, var2 = claim.vars[0], claim.vars[1]       # MENTION order (B1)
    if var1 == var2:
        return Verdict(claim, UNVERIFIED, "Both mentions resolve to the same column.")

    truth = gt.lookup(var1, var2)
    if truth is None:
        reason = gt.untestable_reason(var1, var2)
        return Verdict(claim, UNVERIFIED,
                       f"Pair ('{var1}', '{var2}') could not be tested: {reason or 'not in the ground-truth store'}.")

    support = support_score(truth, cfg)
    t = truth.to_dict()
    checks: dict[str, Any] = {"supported": truth.supported, "q": truth.q, "tier": truth.tier_name}

    if not truth.supported:
        if claim.asserts_null:
            return Verdict(claim, VALID, "Claim of no relationship matches the data "
                           f"(q={truth.q:.3f}, {truth.effect_kind}={truth.effect_abs:.3f}).",
                           truth=t, support=support, checks=checks)
        return Verdict(claim, H_RELATIONSHIP, _no_relationship_reason(truth, cfg, var1, var2),
                       truth=t, support=support, checks=checks)

    if claim.asserts_null:
        return Verdict(claim, H_RELATIONSHIP,
                       f"Claims no relationship, but '{var1}'/'{var2}' show a supported "
                       f"{truth.tier_name} effect ({truth.effect_kind}={truth.effect_abs:.3f}, q={truth.q:.4g}).",
                       truth=t, support=support, checks={**checks, "null_claim": True})

    # ---- direction (only where one exists) ------------------------------------
    d_status, d_reason, d_checked = _check_direction(claim, truth)
    checks["direction_checked"] = d_checked
    if d_status:
        return Verdict(claim, H_DIRECTION, d_reason, truth=t, support=support, checks=checks)

    # ---- magnitude -----------------------------------------------------------------
    m_reason = _check_magnitude(claim, truth, cfg)
    checks["magnitude_checked"] = claim.strength != "unknown" or "r" in claim.value
    if m_reason:
        return Verdict(claim, H_MAGNITUDE, m_reason, truth=t, support=support, checks=checks)

    return Verdict(claim, VALID,
                   f"Consistent with ground truth ({truth.test}, {truth.effect_kind}={truth.effect_abs:.3f}, "
                   f"{truth.tier_name}, q={truth.q:.4g}).",
                   truth=t, support=support, checks=checks)


def _no_relationship_reason(t: PairResult, cfg: PrismaConfig, v1: str, v2: str) -> str:
    if t.q < cfg.alpha:                            # significant but too small to matter
        return (f"Statistically detectable but negligible effect ({t.effect_kind}={t.effect_abs:.3f} < "
                f"{_min_effect(t, cfg):.2f}); not a meaningful relationship between "
                f"'{v1}' and '{v2}'.")
    return (f"No supported relationship between '{v1}' and '{v2}' "
            f"(q={t.q:.3f} >= {cfg.alpha}, {t.effect_kind}={t.effect_abs:.3f}, n={t.n}).")


def _min_effect(t: PairResult, cfg: PrismaConfig) -> float:
    thr = {"r": cfg.r_thresholds, "d": cfg.d_thresholds, "eta2": cfg.eta2_thresholds,
           "w": cfg.w_thresholds}[t.effect_kind]
    return thr[cfg.min_effect_tier - 1]


# -------------------------------------------------------------------------
# Direction
# -------------------------------------------------------------------------
def _check_direction(claim: Claim, t: PairResult) -> tuple[bool, str, bool]:
    """-> (is_error, reason, checked)"""
    # C2 with a named level: "X is higher/lower in <level>"
    if t.claim_type == "C2" and claim.level is not None and claim.level_direction:
        res = _check_level_direction(claim, t)
        if res is not None:
            return res
    if claim.direction == "unknown":
        return False, "", False
    if t.direction is None:                        # no direction defined => never penalise
        return False, "", False
    if claim.direction != t.direction:
        return True, (f"Claimed {claim.direction} relationship, but the data show a {t.direction} one "
                      f"({t.effect_kind}={t.effect:+.3f})."), True
    return False, "", True


def _check_level_direction(claim: Claim, t: PairResult) -> Optional[tuple[bool, str, bool]]:
    lv = str(claim.level)
    # numeric levels are stored as floats ("1.0"): match loosely
    key = next((k for k in t.group_means if k == lv or _same_number(k, lv)), None)
    if key is None:
        return None                                # named level was dropped/absent: fall back
    others = [k for k in t.group_means if k != key]
    if not others:
        return None
    n_out = sum(t.group_ns[k] for k in others)
    mean_out = sum(t.group_means[k] * t.group_ns[k] for k in others) / n_out
    actually_higher = t.group_means[key] > mean_out
    claimed_higher = claim.level_direction == "higher"
    if claimed_higher != actually_higher:
        return True, (f"Claimed {t.num_var} is {claim.level_direction} for '{lv}', but the group mean is "
                      f"{t.group_means[key]:.2f} vs {mean_out:.2f} for the other group(s)."), True
    return False, "", True


def _same_number(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return False


# -------------------------------------------------------------------------
# Magnitude
# -------------------------------------------------------------------------
def _check_magnitude(claim: Claim, t: PairResult, cfg: PrismaConfig) -> Optional[str]:
    # (a) a quoted correlation must be close to the truth (C1 only)
    qr = claim.value.get("r")
    if qr is not None and t.claim_type == "C1":
        cands = [t.effect] + ([t.spearman_rho] if t.spearman_rho is not None else [])
        closest = min(abs(abs(qr) - abs(c)) for c in cands)
        if closest > cfg.numeric_r_abs_tol:
            return (f"Quoted r={qr:+.2f} but actual Pearson r={t.effect:+.2f} "
                    f"(|difference| > {cfg.numeric_r_abs_tol}).")
    # (b) verbal strength vs Cohen tier
    if claim.strength != "unknown":
        claimed = STRENGTH_TO_TIER[claim.strength]
        if abs(claimed - t.tier) >= cfg.magnitude_tier_gap:
            return (f"Claimed '{claim.strength}' but the effect is '{TIER_NAMES[t.tier]}' "
                    f"({t.effect_kind}={t.effect_abs:.3f}).")
    return None


# -------------------------------------------------------------------------
# Descriptive (C4) — reported separately from the taxonomy
# -------------------------------------------------------------------------
def _validate_descriptive(claim: Claim, gt: GroundTruth) -> Verdict:
    cfg = gt.cfg
    keys: list[str] = claim.value.get("stat_keys") or ([claim.stat_key] if claim.stat_key else [])
    nums: list[float] = list(claim.value.get("numbers", []))
    if not keys or not nums:
        return Verdict(claim, UNVERIFIED, "Descriptive claim without a checkable statistic.")

    truths: dict[str, float] = {}
    if keys == ["n_rows"]:
        truths = {"n_rows": float(gt.n_rows), "n_rows_raw": float(gt.n_rows_raw)}
    else:
        col = claim.vars[0]
        ci = gt.schema.columns.get(col)
        if ci is None:
            return Verdict(claim, UNVERIFIED, f"Column '{col}' is excluded from statistics.")
        if "missing" in keys:
            truths["missing"] = float(ci.n_missing)
        if ci.stats:
            for k in keys:
                if k in ("mean", "median", "min", "max", "std"):
                    truths[k] = ci.stats["50%" if k == "median" else k]
    if not truths:
        return Verdict(claim, UNVERIFIED, "No ground-truth statistic available for this claim.")

    tol = cfg.descriptive_rel_tol

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= tol * max(abs(b), 1e-9) or abs(a - b) <= 0.5 * 10 ** -2

    unexplained = [n for n in nums if not any(close(n, tv) for tv in truths.values())]
    checks = {"truth": truths, "numbers": nums}
    if not unexplained:
        return Verdict(claim, VALID, f"Quoted figure(s) match ground truth {truths}.", checks=checks)
    return Verdict(claim, DESC_INCORRECT,
                   f"Quoted figure(s) {unexplained} do not match ground truth {truths}.", checks=checks)
