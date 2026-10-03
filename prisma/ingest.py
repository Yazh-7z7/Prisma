"""
prisma.ingest — cleaning for ground truth (fixes G5).

Rules (HANDOFF §4):
  * NO imputation. Missing stays NaN; every test uses pairwise-complete rows.
  * Identifier columns are excluded from statistics (but remembered, so a claim
    that names one is UNVERIFIED rather than a ghost variable).
  * Physiologically impossible zeros (Pima Glucose, BMI, ...) become NaN.
  * Placeholder strings ("?", "", "N/A") and stray whitespace/tabs (kidney) are cleaned.
  * Columns are typed numeric / binary / categorical; anything else is excluded
    with a recorded reason.  A numeric 0/1 column (Pima ``Outcome``) is BINARY,
    so it gets a group test, not a Pearson correlation.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, PrismaConfig
from .models import BINARY, CATEGORICAL, NUMERIC, ColumnInfo

logger = logging.getLogger("Prisma.Ingest")

_ID_NAME = re.compile(
    r"^(?:unnamed:?\s*0|index|id|row[_\s]?id|record[_\s]?id|patient[_\s]?id|"
    r".*[_\s]id|id[_\s].*)$",
    re.IGNORECASE,
)


class IngestError(ValueError):
    """The dataframe cannot be turned into a usable analysis table."""


@dataclass
class Prepared:
    df: pd.DataFrame                              # cleaned, NaN preserved, IDs/excluded dropped
    columns: dict[str, ColumnInfo]                # analysable columns
    excluded: dict[str, str]                      # column -> reason (id, constant, text, ...)
    all_columns: list[str]                        # every original column name, in order
    report: dict[str, Any] = field(default_factory=dict)

    @property
    def n_rows(self) -> int:
        return int(len(self.df))


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _clean_string_column(s: pd.Series, missing_tokens: set[str]) -> pd.Series:
    def fix(v: Any) -> Any:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        if isinstance(v, str):
            t = v.strip()
            return np.nan if t.lower() in missing_tokens else t
        return v

    return s.astype(object).map(fix)


def _is_sequential_int(s: pd.Series) -> bool:
    x = s.dropna()
    if len(x) < 20 or x.nunique() != len(s):
        return False
    try:
        if not np.all(np.mod(x.astype(float), 1) == 0):
            return False
        d = np.diff(np.sort(x.astype(float).values))
        return bool(np.all(d == 1))
    except Exception:
        return False


def prepare(df: pd.DataFrame, cfg: PrismaConfig = DEFAULT_CONFIG,
            zero_as_missing: tuple[str, ...] | None = None) -> Prepared:
    """Clean *df* for ground-truth computation. Never mutates the input."""
    if df is None or df.empty:
        raise IngestError("The dataframe is empty.")
    if df.shape[0] < 2:
        raise IngestError("Need at least 2 rows.")

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise IngestError("Duplicate column names after stripping whitespace.")
    all_columns = list(df.columns)
    report: dict[str, Any] = {"rows_raw": int(len(df))}

    # --- 1. strings: strip, placeholders -> NaN, numeric coercion ----------
    tokens = {t.lower() for t in cfg.missing_tokens}
    for c in df.columns:
        if pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].astype(float)
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        s = _clean_string_column(df[c], tokens)
        coerced = pd.to_numeric(s, errors="coerce")
        nn = s.notna().sum()
        if nn > 0 and coerced.notna().sum() / nn >= cfg.numeric_coercion_min_fraction:
            df[c] = coerced
        else:
            df[c] = s.map(lambda v: v if (isinstance(v, float) and np.isnan(v)) else str(v))

    # --- 2. duplicates (before IDs are dropped, so identical IDs count) ----
    if cfg.drop_duplicates:
        before = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        report["duplicates_dropped"] = int(before - len(df))
    else:
        report["duplicates_dropped"] = 0

    # --- 3. zeros that mean "missing" --------------------------------------
    targets = {_norm_name(z) for z in (zero_as_missing if zero_as_missing is not None
                                       else cfg.zero_as_missing)}
    zero_counts: dict[str, int] = {}
    for c in df.columns:
        if _norm_name(c) in targets and pd.api.types.is_numeric_dtype(df[c]):
            mask = df[c] == 0
            k = int(mask.sum())
            if k:
                df.loc[mask, c] = np.nan
                zero_counts[c] = k
    report["zeros_to_nan"] = zero_counts

    # --- 4. exclude / type columns -----------------------------------------
    excluded: dict[str, str] = {}
    columns: dict[str, ColumnInfo] = {}
    n_rows = len(df)
    for c in all_columns:
        s = df[c]
        nn = int(s.notna().sum())
        nunique = int(s.nunique(dropna=True))
        if _ID_NAME.match(c) or (pd.api.types.is_numeric_dtype(s) and _is_sequential_int(s)):
            excluded[c] = "identifier column"
            continue
        if nn == 0:
            excluded[c] = "all values missing"
            continue
        if nunique <= 1:
            excluded[c] = "constant column"
            continue

        if pd.api.types.is_numeric_dtype(s):
            if nunique == 2:
                lv = sorted(s.dropna().unique().tolist())
                columns[c] = ColumnInfo(
                    name=c, kind=BINARY, n_valid=nn, n_missing=n_rows - nn,
                    levels=lv, ordered=True,
                    level_counts={str(v): int((s == v).sum()) for v in lv},
                    stats=_numeric_stats(s),
                )
            else:
                columns[c] = ColumnInfo(name=c, kind=NUMERIC, n_valid=nn,
                                        n_missing=n_rows - nn, stats=_numeric_stats(s))
        else:
            if nunique > cfg.max_categorical_levels or nunique == nn:
                excluded[c] = f"free text / high cardinality ({nunique} levels)"
                continue
            lv = sorted(s.dropna().unique().tolist())
            kind = BINARY if nunique == 2 else CATEGORICAL
            columns[c] = ColumnInfo(
                name=c, kind=kind, n_valid=nn, n_missing=n_rows - nn, levels=lv,
                ordered=False, level_counts={str(v): int((s == v).sum()) for v in lv},
            )

    if len(columns) < 2:
        raise IngestError(
            f"Fewer than 2 analysable columns remain (excluded: {excluded})."
        )

    keep = [c for c in all_columns if c in columns]
    report["rows"] = int(n_rows)
    report["n_columns_raw"] = len(all_columns)
    report["n_columns_analysed"] = len(columns)
    report["excluded"] = dict(excluded)
    report["kinds"] = {c: ci.kind for c, ci in columns.items()}
    report["missing"] = {c: ci.n_missing for c, ci in columns.items() if ci.n_missing}
    logger.info("Prepared %d rows, %d/%d columns analysable", n_rows, len(columns), len(all_columns))
    return Prepared(df=df[keep].copy(), columns=columns, excluded=excluded,
                    all_columns=all_columns, report=report)


def _numeric_stats(s: pd.Series) -> dict[str, float]:
    x = s.dropna().astype(float)
    if x.empty:
        return {}
    q = x.quantile([0.25, 0.5, 0.75])
    return {
        "count": float(len(x)), "mean": float(x.mean()),
        "std": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
        "min": float(x.min()), "25%": float(q.loc[0.25]), "50%": float(q.loc[0.5]),
        "75%": float(q.loc[0.75]), "max": float(x.max()),
    }
