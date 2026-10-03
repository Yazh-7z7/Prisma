"""
prisma.ground_truth — Ground-Truth engine v2 (fixes G4, G5; design decision 3).

* Stores EVERY tested pair (not only significant ones): n, test, effect size on
  Cohen's scale, raw p, BH-FDR q, signed direction.
* Pairs that cannot be tested are recorded with a reason in ``untestable``.
  The validator maps  tested&null -> HALLUCINATION_RELATIONSHIP  and
  not testable -> UNVERIFIED.  "Never tested" can no longer masquerade as "null".
* One FDR family: all tested pairs of the dataset (Benjamini-Hochberg).
* Effect sizes: Pearson r (C1); Cohen's d (2 groups) / eta^2 (>=3 groups) (C2);
  Cramer's V -> Cohen's w (C3).  Tiers come from PrismaConfig only.
* Deterministic: no randomness anywhere.
"""
from __future__ import annotations

import itertools
import logging
import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

from .aliases import AliasMap, build_alias_map
from .config import DEFAULT_CONFIG, PrismaConfig
from .ingest import Prepared, prepare
from .models import BINARY, CATEGORICAL, NUMERIC, TIER_NAMES, ColumnInfo, PairResult

logger = logging.getLogger("Prisma.GroundTruth")


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def tier_of(value: float, thresholds: tuple[float, float, float]) -> int:
    """0 negligible, 1 small(weak), 2 medium(moderate), 3 large(strong)."""
    v = abs(value)
    if v < thresholds[0]:
        return 0
    if v < thresholds[1]:
        return 1
    if v < thresholds[2]:
        return 2
    return 3


@dataclass
class Schema:
    """What the parser needs to know about the dataset."""
    columns: dict[str, ColumnInfo]
    excluded: dict[str, str]
    all_columns: list[str]
    aliases: AliasMap


@dataclass
class GroundTruth:
    cfg: PrismaConfig
    schema: Schema
    pairs: dict[tuple[str, str], PairResult]
    untestable: dict[tuple[str, str], str]
    n_rows: int
    n_rows_raw: int
    summary: dict[str, dict[str, Any]]
    report: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------- lookup
    def lookup(self, a: str, b: str) -> Optional[PairResult]:
        return self.pairs.get(pair_key(a, b))

    def untestable_reason(self, a: str, b: str) -> Optional[str]:
        return self.untestable.get(pair_key(a, b))

    def supported_pairs(self) -> list[PairResult]:
        return sorted((p for p in self.pairs.values() if p.supported),
                      key=lambda p: (-p.tier, -p.effect_r))

    @property
    def n_tests(self) -> int:
        return len(self.pairs)

    # -------------------------------------------------------------- prompts
    def to_prompt_block(self, max_supported: int = 40, max_null: int = 15) -> str:
        """The ground-truth text shown to the LLM (G1/G2 fix).

        Ranked by effect size (not store order), includes direction for C1 and
        the higher group for C2, categorical associations, AND a sample of
        tested-null pairs so the model learns what is NOT supported.
        """
        lines: list[str] = []
        c = self.cfg
        lines.append(
            f"DATASET: {self.n_rows} rows. Statistics use pairwise-complete rows; "
            f"significance = BH-FDR q < {c.alpha}; effect sizes follow Cohen's conventions."
        )
        lines.append("COLUMNS (type; summary):")
        for name, ci in self.schema.columns.items():
            if ci.kind == NUMERIC or (ci.kind == BINARY and ci.ordered):
                s = ci.stats
                lines.append(
                    f"  - {name} [{ci.kind}]: mean={s.get('mean', float('nan')):.2f}, "
                    f"std={s.get('std', float('nan')):.2f}, min={s.get('min', float('nan')):.2f}, "
                    f"max={s.get('max', float('nan')):.2f}, missing={ci.n_missing}"
                )
            else:
                lv = ", ".join(f"{k}={v}" for k, v in list(ci.level_counts.items())[:6])
                lines.append(f"  - {name} [{ci.kind}]: levels {lv}; missing={ci.n_missing}")

        sup = self.supported_pairs()[:max_supported]
        lines.append(f"SUPPORTED RELATIONSHIPS ({len(self.supported_pairs())} total; strongest first):")
        for p in sup:
            lines.append("  - " + _describe_pair(p))
        nulls = sorted((p for p in self.pairs.values() if not p.supported),
                       key=lambda p: p.q if not math.isnan(p.q) else 1.0, reverse=True)[:max_null]
        if nulls:
            lines.append("TESTED BUT NOT SUPPORTED (do not claim these):")
            for p in nulls:
                lines.append(f"  - {p.var1} vs {p.var2}: no supported relationship "
                             f"(q={p.q:.3f}, effect {p.effect_kind}={p.effect_abs:.3f})")
        return "\n".join(lines)

    # ------------------------------------------------------------ serialisers
    def to_legacy_dict(self) -> dict[str, Any]:
        """Backward-compatible dict for the FastAPI/Next.js layer (supported pairs only,
        plus the full store under ``pairs``)."""
        corr, grp, cat = [], [], []
        for p in self.supported_pairs():
            conf = _support_from_pair(p, self.cfg)
            if p.claim_type == "C1":
                corr.append({
                    "var1": p.var1, "var2": p.var2,
                    "pearson": {"r": round(p.effect, 4), "p": p.p},
                    "spearman": {"r": _r4(p.spearman_rho), "p": p.spearman_p},
                    "correlation": round(p.effect, 4), "p_value": p.p, "q_value": p.q,
                    "n": p.n, "strength": TIER_NAMES[p.tier], "direction": p.direction,
                    "confidence": conf, "type": "correlation",
                })
            elif p.claim_type == "C2":
                grp.append({
                    "var1": p.cat_var, "var2": p.num_var, "variable": p.num_var,
                    "group_by": p.cat_var, "test": p.test, "p_value": p.p, "q_value": p.q,
                    "effect_size": round(p.effect_abs, 4), "effect_kind": p.effect_kind,
                    "n": p.n, "strength": TIER_NAMES[p.tier],
                    "direction": p.direction or f"{p.higher_group} higher",
                    "higher_group": p.higher_group, "significant": True,
                    "group_means": p.group_means, "confidence": conf,
                    "type": "group_difference",
                })
            else:
                cat.append({
                    "var1": p.var1, "var2": p.var2, "test": p.test, "p_value": p.p,
                    "q_value": p.q, "cramers_v": p.cramers_v, "n": p.n,
                    "strength": TIER_NAMES[p.tier], "direction": p.direction or "associated",
                    "confidence": conf, "type": "categorical_association",
                })
        return {
            "summary": {"stats": self.summary,
                        "dtypes": {c: ci.kind for c, ci in self.schema.columns.items()}},
            "correlations": corr, "group_differences": grp, "categorical_associations": cat,
            "n_tests": self.n_tests, "n_supported": len(self.supported_pairs()),
            "n_untestable": len(self.untestable),
            "pairs": [p.to_dict() for p in self.pairs.values()],
            "preprocessing": self.report,
            "config_hash": self.cfg.hash(),
        }


def _r4(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(float(x), 4)


def _describe_pair(p: PairResult) -> str:
    if p.claim_type == "C1":
        return (f"{p.var1} vs {p.var2}: {p.direction} correlation, r={p.effect:+.2f} "
                f"({p.tier_name}), q={p.q:.4f}, n={p.n}")
    if p.claim_type == "C2":
        means = ", ".join(f"{g}={m:.2f}" for g, m in p.group_means.items())
        dirn = f" ({p.direction})" if p.direction else ""
        return (f"{p.num_var} differs by {p.cat_var}{dirn}: {p.effect_kind}={p.effect_abs:.2f} "
                f"({p.tier_name}), q={p.q:.4f}; group means {means}; higher in {p.higher_group}")
    return (f"{p.var1} associated with {p.var2}: Cramer's V={p.cramers_v:.2f} "
            f"({p.tier_name}), q={p.q:.4f}, n={p.n}")


def _support_from_pair(p: PairResult, cfg: PrismaConfig) -> float:
    from .support import support_score
    return support_score(p, cfg)


# =========================================================================
#  Engine
# =========================================================================
def build_ground_truth(data: pd.DataFrame | Prepared,
                       cfg: PrismaConfig = DEFAULT_CONFIG,
                       extra_aliases: dict | None = None,
                       alias_preset: str | None = "auto") -> GroundTruth:
    prep = data if isinstance(data, Prepared) else prepare(data, cfg)
    df = prep.df
    cols = prep.columns
    num = [c for c, ci in cols.items() if ci.kind == NUMERIC]
    catlike = [c for c, ci in cols.items() if ci.kind in (BINARY, CATEGORICAL)]

    results: list[PairResult] = []
    untestable: dict[tuple[str, str], str] = {}

    # ---- C1: numeric x numeric ------------------------------------------------
    for a, b in itertools.combinations(num, 2):
        r = _test_correlation(df, a, b, cfg)
        _collect(r, a, b, results, untestable)

    # ---- C2: numeric x (binary|categorical) -------------------------------------
    numeric_like = num  # binary-numeric columns are grouping variables, not outcomes
    for n_col in numeric_like:
        for c_col in catlike:
            r = _test_group(df, n_col, c_col, cols[c_col], cfg)
            _collect(r, n_col, c_col, results, untestable)

    # ---- C3: (binary|categorical) x (binary|categorical) -------------------------
    for a, b in itertools.combinations(catlike, 2):
        r = _test_association(df, a, b, cols[a], cols[b], cfg)
        _collect(r, a, b, results, untestable)

    # ---- BH-FDR over the single family of tested pairs ---------------------------
    if results:
        pvals = np.array([r.p for r in results], dtype=float)
        qvals = stats.false_discovery_control(pvals, method="bh")
        for r, q in zip(results, qvals):
            r.q = float(q)
            r.supported = bool(q < cfg.alpha and r.tier >= cfg.min_effect_tier)

    pairs = {pair_key(r.var1, r.var2): r for r in results}
    summary = {c: _column_summary(df, ci) for c, ci in cols.items()}
    schema = Schema(columns=cols, excluded=prep.excluded, all_columns=prep.all_columns,
                    aliases=build_alias_map(prep, extra_aliases, alias_preset))
    gt = GroundTruth(
        cfg=cfg, schema=schema, pairs=pairs, untestable=untestable,
        n_rows=prep.n_rows, n_rows_raw=prep.report.get("rows_raw", prep.n_rows),
        summary=summary, report=prep.report,
    )
    logger.info("Ground truth: %d tested, %d supported, %d untestable",
                gt.n_tests, len(gt.supported_pairs()), len(untestable))
    return gt


def _collect(r: PairResult | str, a: str, b: str, results: list[PairResult],
             untestable: dict[tuple[str, str], str]) -> None:
    if isinstance(r, str):
        untestable[pair_key(a, b)] = r
    else:
        results.append(r)


# ------------------------------------------------------------------ C1
def _test_correlation(df: pd.DataFrame, a: str, b: str, cfg: PrismaConfig) -> PairResult | str:
    tmp = df[[a, b]].dropna()
    n = len(tmp)
    if n < cfg.min_pair_n:
        return f"only {n} pairwise-complete rows (< {cfg.min_pair_n})"
    x, y = tmp[a].astype(float).values, tmp[b].astype(float).values
    if np.std(x) == 0 or np.std(y) == 0:
        return "a column is constant on the pairwise-complete rows"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r, p = stats.pearsonr(x, y)
            rho, p_s = stats.spearmanr(x, y)
    except Exception as exc:  # pragma: no cover - scipy internal failures
        return f"correlation failed: {exc}"
    if not (np.isfinite(r) and np.isfinite(p)):
        return "non-finite correlation"
    return PairResult(
        var1=a, var2=b, claim_type="C1", test="pearson", n=n,
        effect_kind="r", effect=float(r), effect_abs=abs(float(r)), effect_r=abs(float(r)),
        tier=tier_of(r, cfg.r_thresholds), p=float(p),
        direction="positive" if r > 0 else "negative",
        spearman_rho=float(rho) if np.isfinite(rho) else None,
        spearman_p=float(p_s) if np.isfinite(p_s) else None,
    )


# ------------------------------------------------------------------ C2
def _test_group(df: pd.DataFrame, num_col: str, cat_col: str, cat_info: ColumnInfo,
                cfg: PrismaConfig) -> PairResult | str:
    tmp = df[[num_col, cat_col]].dropna()
    groups: dict[Any, np.ndarray] = {}
    dropped: list[str] = []
    for lv, sub in tmp.groupby(cat_col, sort=True):
        vals = sub[num_col].astype(float).values
        if len(vals) >= cfg.min_group_n:
            groups[lv] = vals
        else:
            dropped.append(str(lv))
    if len(groups) < 2:
        return f"fewer than 2 groups with >= {cfg.min_group_n} rows"
    levels = list(groups.keys())
    arrays = [groups[k] for k in levels]
    n = int(sum(len(a) for a in arrays))
    if n < cfg.min_pair_n:
        return f"only {n} rows in usable groups"
    if all(np.std(a) == 0 for a in arrays) and len({float(a[0]) for a in arrays}) == 1:
        return "no variation in the numeric column"

    means = {str(k): float(np.mean(v)) for k, v in groups.items()}
    ns = {str(k): int(len(v)) for k, v in groups.items()}
    higher = max(means, key=means.get)  # type: ignore[arg-type]

    grand = np.concatenate(arrays)
    ss_total = float(((grand - grand.mean()) ** 2).sum())
    ss_between = float(sum(len(a) * (a.mean() - grand.mean()) ** 2 for a in arrays))
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if len(arrays) == 2:
                lo, hi = arrays[0], arrays[1]
                t, p = stats.ttest_ind(lo, hi, equal_var=False)
                sp = math.sqrt(((len(lo) - 1) * np.var(lo, ddof=1) +
                                (len(hi) - 1) * np.var(hi, ddof=1)) / (len(lo) + len(hi) - 2))
                if sp == 0:
                    return "zero pooled variance"
                d = (float(np.mean(hi)) - float(np.mean(lo))) / sp   # hi level minus lo level
                test, kind, eff, eff_abs = "welch-t", "d", d, abs(d)
                tier = tier_of(d, cfg.d_thresholds)
                eff_r = abs(d) / math.sqrt(d * d + 4.0)
                direction = None
                if cat_info.ordered:
                    direction = "positive" if d > 0 else "negative"
            else:
                f, p = stats.f_oneway(*arrays)
                test, kind, eff, eff_abs = "anova", "eta2", eta2, eta2
                tier = tier_of(eta2, cfg.eta2_thresholds)
                eff_r = math.sqrt(max(eta2, 0.0))
                direction = None
    except Exception as exc:
        return f"group test failed: {exc}"
    if not np.isfinite(p):
        return "non-finite p-value"

    return PairResult(
        var1=num_col, var2=cat_col, claim_type="C2", test=test, n=n,
        effect_kind=kind, effect=float(eff), effect_abs=float(eff_abs), effect_r=float(eff_r),
        tier=tier, p=float(p), direction=direction, num_var=num_col, cat_var=cat_col,
        group_means=means, group_ns=ns, higher_group=higher, dropped_groups=dropped,
        eta2=float(eta2),
    )


# ------------------------------------------------------------------ C3
def _test_association(df: pd.DataFrame, a: str, b: str, ia: ColumnInfo, ib: ColumnInfo,
                      cfg: PrismaConfig) -> PairResult | str:
    tmp = df[[a, b]].dropna()
    table = pd.crosstab(tmp[a], tmp[b])
    n = int(table.values.sum())
    if table.shape[0] < 2 or table.shape[1] < 2:
        return "fewer than 2 levels on the pairwise-complete rows"
    if n < cfg.min_pair_n:
        return f"only {n} pairwise-complete rows (< {cfg.min_pair_n})"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chi2_nc, p_nc, _, expected = stats.chi2_contingency(table, correction=False)
            if table.shape == (2, 2):
                if expected.min() < 5:
                    p = float(stats.fisher_exact(table.values)[1])
                    test = "fisher"
                else:
                    p = float(stats.chi2_contingency(table, correction=True)[1])  # Yates
                    test = "chi2"
            else:
                p, test = float(p_nc), "chi2"
    except Exception as exc:
        return f"association test failed: {exc}"
    if not np.isfinite(p):
        return "non-finite p-value"

    min_dim = min(table.shape) - 1
    v = math.sqrt(chi2_nc / (n * min_dim)) if min_dim > 0 else 0.0
    w = v * math.sqrt(min_dim)
    direction = None
    if table.shape == (2, 2) and ia.ordered and ib.ordered:
        t = table.values
        direction = "positive" if t[0, 0] * t[1, 1] > t[0, 1] * t[1, 0] else "negative"
    low = bool((expected < 5).mean() > 0.2)
    return PairResult(
        var1=a, var2=b, claim_type="C3", test=test, n=n, effect_kind="w",
        effect=float(w), effect_abs=float(w), effect_r=float(min(v, 1.0)),
        tier=tier_of(w, cfg.w_thresholds), p=p, direction=direction,
        cramers_v=float(v), low_expected_counts=low,
    )


# ------------------------------------------------------------------ summary
def _column_summary(df: pd.DataFrame, ci: ColumnInfo) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": ci.kind, "n_valid": ci.n_valid, "n_missing": ci.n_missing}
    if ci.stats:
        out.update(ci.stats)
    if ci.level_counts:
        out["level_counts"] = dict(ci.level_counts)
    return out
