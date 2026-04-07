"""SafeClaw 合同测试。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_CHECKS_ROOT = REPO_ROOT / "tools" / "checks"

for entry in (REPO_ROOT, TOOLS_CHECKS_ROOT):
    entry_text = str(entry)
    if entry_text not in sys.path:
        sys.path.insert(0, entry_text)

__all__ = ["REPO_ROOT", "TOOLS_CHECKS_ROOT"]
