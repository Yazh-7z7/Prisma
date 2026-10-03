"""
backend/parser.py — DEPRECATED SHIM.

All parsing logic lives in ``prisma.parser`` (Parser v2). This module only
re-exports it so older imports keep working. Do not add logic here.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from prisma.parser import parse_insights  # noqa: E402,F401
