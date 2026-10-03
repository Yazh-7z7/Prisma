"""
backend/validator.py — DEPRECATED SHIM.

All validation logic lives in ``prisma.validator`` (Validator v2).
Re-exported only for backward compatibility. Do not add logic here.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from prisma.validator import validate_claim, validate_claims  # noqa: E402,F401
