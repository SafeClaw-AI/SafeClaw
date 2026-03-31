from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mvp.chancellor_panel import (  # noqa: E402
    build_chancellor_status_snapshot,
    derive_chancellor_stability,
)


class ChancellorPanelTest(unittest.TestCase):
    def test_build_chancellor_status_snapshot_uses_current_truth_sources(self) -> None:
        snapshot = build_chancellor_status_snapshot()
        self.assertEqual(
            snapshot,
            {
                "mode": "M2-2 丞相状态聚合",
                "stability": "稳态",
                "next_step": "把 mode/stability/next_step/summary 接到命令级消费入口",
                "summary": "当前处于 M2-2 丞相状态聚合；状态稳态；下一步把 mode/stability/next_step/summary 接到命令级消费入口",
            },
        )

    def test_derive_chancellor_stability_prefers_blocker_then_graduated_then_tail(self) -> None:
        self.assertEqual(derive_chancellor_stability("存在阻塞，需先修复"), "存在阻塞")
        self.assertEqual(derive_chancellor_stability("M1b 已毕业，毕业链全绿"), "稳态")
        self.assertEqual(derive_chancellor_stability("已进入 M1b 收口尾段，继续推进"), "收口中")
        self.assertEqual(derive_chancellor_stability("普通推进中"), "推进中")


if __name__ == "__main__":
    unittest.main()
