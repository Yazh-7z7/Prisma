"""
prisma.support — statistical SUPPORT score (decision 8: renamed from "confidence").

    support = w_sig * (1 - q) + w_effect * effect_r        clamped to [0.01, 0.99]

q        BH-FDR adjusted p-value of the claimed pair (paper used raw Pearson p)
effect_r r-equivalent effect size in [0,1]: |r| (C1), |d|/sqrt(d^2+4) or sqrt(eta^2) (C2),
         Cramer's V (C3)

This is an UNCALIBRATED heuristic ranking score, not a probability that a claim
is true. It is evaluated empirically (AUROC / calibration, Phase 6), never
asserted. It is None for claims with no ground-truth entry.
"""
from __future__ import annotations

import math

from .config import DEFAULT_CONFIG, PrismaConfig
from .models import PairResult


def support_score(p: PairResult, cfg: PrismaConfig = DEFAULT_CONFIG) -> float:
    q = p.q if not math.isnan(p.q) else p.p
    sig = 1.0 - min(max(q, 0.0), 1.0)
    eff = min(max(p.effect_r, 0.0), 1.0)
    score = cfg.support_w_sig * sig + cfg.support_w_effect * eff
    return round(min(max(score, 0.01), 0.99), 3)
