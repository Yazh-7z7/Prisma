"""
data_ingestion.py — Data Ingestion Service
Prisma | Production-Grade Backend

Responsibilities:
  - Accept uploaded File objects (CSV / XLSX)
  - Validate structure and encoding
  - Normalize column names
  - Return a clean pandas DataFrame + metadata dict
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("Prisma.DataIngestion")

# ---------------------------------------------------------------------------
# Supported file types
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class DataIngestionError(ValueError):
    """Raised when the uploaded file cannot be ingested."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_file(filename: str, content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Main entry point.

    Parameters
    ----------
    filename : str
        Original filename from the upload (used to detect file type).
    content  : bytes
        Raw file bytes.

    Returns
    -------
    (df, metadata)
        df       — clean, normalised DataFrame
        metadata — dict with shape, dtypes, missing counts, column names
    """
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise DataIngestionError(
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    try:
        if suffix == ".csv":
            df = _read_csv(content)
        else:
            df = _read_excel(content)
    except DataIngestionError:
        raise
    except Exception as exc:
        raise DataIngestionError(f"Failed to parse file: {exc}") from exc

    _validate(df)
    df = _normalise(df)
    metadata = _build_metadata(df, filename)

    logger.info(
        "Ingested '%s': %d rows × %d columns", filename, df.shape[0], df.shape[1]
    )
    return df, metadata


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_csv(content: bytes) -> pd.DataFrame:
    """Try UTF-8 then latin-1 fallback."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except UnicodeDecodeError:
            continue
    raise DataIngestionError("Cannot decode CSV — try saving as UTF-8.")


def _read_excel(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:
        raise DataIngestionError(f"Excel read error: {exc}") from exc


def _validate(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        raise DataIngestionError("The file is empty.")
    if len(df.columns) == 0:
        raise DataIngestionError("The file has no columns.")
    if len(df) < 2:
        raise DataIngestionError("The file must contain at least 2 data rows.")


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Strip whitespace from string columns
    - Attempt numeric coercion for object columns that look numeric
    - Drop fully-duplicate rows
    """
    # Normalise column names: strip + collapse spaces
    df.columns = [str(c).strip().replace("  ", " ") for c in df.columns]

    # Attempt numeric coercion on object columns
    for col in df.select_dtypes(include="object").columns:
        # Safely strip only elements that are actually strings
        stripped_series = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
        
        converted = pd.to_numeric(stripped_series, errors="coerce")
        if converted.notna().sum() / max(len(df), 1) > 0.8:
            df[col] = converted
        else:
            df[col] = stripped_series

    # Drop fully-duplicate rows
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    if dropped:
        logger.debug("Dropped %d duplicate rows.", dropped)

    return df.reset_index(drop=True)


def _build_metadata(df: pd.DataFrame, filename: str) -> dict[str, Any]:
    return {
        "filename": filename,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_counts": df.isna().sum().to_dict(),
        "missing_total": int(df.isna().sum().sum()),
        "numeric_columns": list(df.select_dtypes(include="number").columns),
        "categorical_columns": list(df.select_dtypes(include=["object", "category", "bool"]).columns),
    }
