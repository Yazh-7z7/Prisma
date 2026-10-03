"""
prisma.config — the ONE configuration object used by every stage.

Design decision 6 (HANDOFF): thresholds are Cohen's conventions, defined once.
No other module may hard-code a threshold; they all read this object.

The config is frozen and hashable so a run log can store ``cfg.hash()`` and
anyone can verify which settings produced a paper number.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PrismaConfig:
    # ---- inference -------------------------------------------------------
    alpha: float = 0.05                       # applied to BH-FDR adjusted q
    min_pair_n: int = 10                      # min pairwise-complete rows to test
    min_group_n: int = 5                      # min rows per group in a group test
    max_categorical_levels: int = 20          # above this a text column is excluded

    # ---- Cohen (1988) effect-size tiers: (small, medium, large) ------------
    r_thresholds: tuple[float, float, float] = (0.1, 0.3, 0.5)
    d_thresholds: tuple[float, float, float] = (0.2, 0.5, 0.8)
    eta2_thresholds: tuple[float, float, float] = (0.01, 0.06, 0.14)
    w_thresholds: tuple[float, float, float] = (0.1, 0.3, 0.5)   # Cohen's w = V*sqrt(df*)

    # VALID needs q < alpha AND effect tier >= this (1 = "small").
    min_effect_tier: int = 1
    # MAGNITUDE error only when claimed and actual tiers differ by >= this
    # (paper: "only serious mismatches are flagged").
    magnitude_tier_gap: int = 2
    # If a claim quotes a number for r, it must be within this of the truth.
    numeric_r_abs_tol: float = 0.15
    # Descriptive claims (C4): relative tolerance on quoted figures.
    descriptive_rel_tol: float = 0.05

    # ---- support score (renamed from "confidence", decision 8) ------------
    support_w_sig: float = 0.6
    support_w_effect: float = 0.4

    # ---- ingest -----------------------------------------------------------
    drop_duplicates: bool = True
    # Columns where a literal 0 is physiologically impossible => missing.
    # Matched case-insensitively on alphanumerics only ("Blood Pressure" == "bloodpressure").
    zero_as_missing: tuple[str, ...] = (
        "glucose", "bloodpressure", "skinthickness", "insulin", "bmi",
    )
    missing_tokens: tuple[str, ...] = ("", "?", "na", "n/a", "nan", "null", "-", "--")
    numeric_coercion_min_fraction: float = 0.8

    # ---- parser -----------------------------------------------------------
    # Slot-based ghost detection is heuristic; keep it switchable so the
    # error-injection benchmark (P5) can report its precision/recall.
    ghost_slot_detection: bool = True
    ghost_identifier_detection: bool = True
    fuzzy_token_ratio: float = 0.85           # single-token typo tolerance

    # ------------------------------------------------------------------ utils
    def snapshot(self) -> dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        blob = json.dumps(self.snapshot(), sort_keys=True, default=list)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any] | None) -> "PrismaConfig":
        """Build from a (possibly partial) mapping; unknown keys are an error
        so a typo in config.yaml cannot silently change an experiment."""
        if not m:
            return cls()
        known = {f.name for f in fields(cls)}
        unknown = set(m) - known
        if unknown:
            raise ValueError(f"Unknown PrismaConfig keys: {sorted(unknown)}")
        kwargs = {}
        for k, v in m.items():
            kwargs[k] = tuple(v) if isinstance(v, list) else v
        return cls(**kwargs)

    @classmethod
    def from_yaml(cls, path: str | Path, section: str = "prisma") -> "PrismaConfig":
        import yaml  # local import: core stays importable without PyYAML

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_mapping(data.get(section))


DEFAULT_CONFIG = PrismaConfig()
