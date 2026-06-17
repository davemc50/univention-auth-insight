# SPDX-License-Identifier: AGPL-3.0-only
"""Make umc.python.authin importable in unit tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "umc" / "python"))
