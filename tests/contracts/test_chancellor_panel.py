"""Legacy Chancellor compatibility contracts.

SafeClaw 当前不单独开发丞相模式/大都督模式等外部解释层功能。
若后续需要接入，只做外部程序拼接融合，不在 SafeClaw 仓内继续扩写独立模式功能。
本文件只锁历史兼容快照，避免旧行为无意漂移。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.mvp.chancellor_panel as chancellor_panel_module  # noqa: E402
from tools.mvp.chancellor_panel import (  # noqa: E402
    build_chancellor_panel_command_payload,
    build_chancellor_status_snapshot,
    derive_chancellor_stability,
)


class ChancellorPanelTest(unittest.TestCase):
    def test_chancellor_module_docstring_states_external_integration_boundary(self) -> None:
        module_doc = chancellor_panel_module.__doc__ or ""
        self.assertIn("SafeClaw 当前不单独开发丞相模式/大都督模式等外部解释层功能。", module_doc)
        self.assertIn("只做外部程序拼接融合", module_doc)

    def test_build_chancellor_status_snapshot_uses_current_truth_sources(self) -> None:
        snapshot = build_chancellor_status_snapshot()
        self.assertEqual(
            snapshot,
            {
                "mode": "M2-P0-4 产品价值闭环验收",
                "stability": "稳态",
                "next_step": "继续推进 M2-P0-4 产品价值闭环验收",
                "summary": "当前处于 M2-P0-4 产品价值闭环验收；状态稳态；下一步继续推进 M2-P0-4 产品价值闭环验收",
            },
        )

    def test_build_chancellor_panel_command_payload_promotes_summary_then_fields(self) -> None:
        payload = build_chancellor_panel_command_payload(
            "  丞相状态  ",
            dev_plan_text=(
                "当前主线：`M2-2 丞相状态聚合`\n"
                "当前阶段：`M1b` 已毕业；`M2-2` 已接入命令级消费入口，下一步切到 `M2-3 丞相检查最小检查`\n"
            ),
        )
        self.assertEqual(
            payload,
            {
                "command": "丞相状态",
                "summary": "当前处于 M2-2 丞相状态聚合；状态稳态；下一步切到 M2-3 丞相检查最小检查",
                "mode": "M2-2 丞相状态聚合",
                "stability": "稳态",
                "next_step": "切到 M2-3 丞相检查最小检查",
            },
        )

    def test_build_chancellor_panel_command_payload_rejects_unknown_command(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported chancellor panel command"):
            build_chancellor_panel_command_payload("丞相帮助")

    def test_derive_chancellor_stability_prefers_blocker_then_graduated_then_tail(self) -> None:
        self.assertEqual(derive_chancellor_stability("存在阻塞，需先修复"), "存在阻塞")
        self.assertEqual(derive_chancellor_stability("M1b 已毕业，毕业链全绿"), "稳态")
        self.assertEqual(derive_chancellor_stability("已进入 M1b 收口尾段，继续推进"), "收口中")
        self.assertEqual(derive_chancellor_stability("普通推进中"), "推进中")


if __name__ == "__main__":
    unittest.main()
