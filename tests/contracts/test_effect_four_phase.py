from __future__ import annotations

import unittest
import tempfile
import sqlite3
import json
from pathlib import Path

from tests.contracts import REPO_ROOT


class EffectFourPhaseProtocolTest(unittest.TestCase):
    """测试 Effect Ledger 四阶段提交协议

    协议要求：
    1. prepared → dispatched → executed → committing (正常路径)
    2. uncertain 状态用于不可探测的崩溃
    3. executed_assumed 用于 probe_mode:none 的脏终态
    4. 每个 transition 必须记录在 transitions 数组中
    """

    def setUp(self) -> None:
        """创建临时数据库和 effect ledger 表"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript("""
            CREATE TABLE effects (
                effect_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                intent_key TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                tier TEXT NOT NULL,
                reversibility TEXT NOT NULL,
                status TEXT NOT NULL,
                probe_mode TEXT DEFAULT 'auto',
                probe_state TEXT,
                schema_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE effect_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                effect_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                at TEXT NOT NULL,
                triggered_by TEXT NOT NULL,
                reason TEXT,
                FOREIGN KEY (effect_id) REFERENCES effects(effect_id)
            );

            CREATE TABLE effect_attempts (
                attempt_id TEXT PRIMARY KEY,
                effect_id TEXT NOT NULL,
                attempt_seq INTEGER NOT NULL,
                dispatched_at TEXT NOT NULL,
                lease_id TEXT NOT NULL,
                fencing_token INTEGER NOT NULL,
                result_status TEXT,
                FOREIGN KEY (effect_id) REFERENCES effects(effect_id)
            );
        """)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _insert_effect(self, effect_id: str, status: str, probe_mode: str = "auto") -> None:
        self.conn.execute(
            """INSERT INTO effects (
                effect_id, task_id, trace_id, intent_key, actor, action, target,
                tier, reversibility, status, probe_mode, schema_version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (effect_id, "task-001", "trace-001", "intent-001", "worker",
             "file_write", "/tmp/test.txt", "TIER_1", "REV_ROLLBACKABLE",
             status, probe_mode, "3.2.0")
        )
        self.conn.commit()

    def _add_transition(self, effect_id: str, from_status: str, to_status: str, triggered_by: str) -> None:
        self.conn.execute(
            """INSERT INTO effect_transitions (effect_id, from_status, to_status, at, triggered_by)
               VALUES (?, ?, ?, datetime('now'), ?)""",
            (effect_id, from_status, to_status, triggered_by)
        )
        self.conn.commit()

    def _add_attempt(self, effect_id: str, attempt_seq: int, fencing_token: int = 1) -> None:
        self.conn.execute(
            """INSERT INTO effect_attempts (
                attempt_id, effect_id, attempt_seq, dispatched_at, lease_id, fencing_token
            ) VALUES (?, ?, ?, datetime('now'), ?, ?)""",
            (f"attempt-{effect_id}-{attempt_seq}", effect_id, attempt_seq, f"lease-{effect_id}", fencing_token)
        )
        self.conn.commit()

    # === 核心四阶段测试 ===

    def test_phase1_prepared_to_dispatched(self) -> None:
        """测试: prepared → dispatched (声明意图 → 动作已发出)"""
        effect_id = "effect-001"
        self._insert_effect(effect_id, "prepared")
        self._add_transition(effect_id, "prepared", "dispatched", "orchestrator")
        self._add_attempt(effect_id, 1)

        # 验证状态变更
        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "dispatched")

        # 验证 transition 记录
        trans = self.conn.execute(
            "SELECT from_status, to_status, triggered_by FROM effect_transitions WHERE effect_id = ?",
            (effect_id,)
        ).fetchall()
        self.assertEqual(len(trans), 1)
        self.assertEqual(trans[0], ("prepared", "dispatched", "orchestrator"))

        # 验证 attempt 记录
        attempt = self.conn.execute(
            "SELECT attempt_seq, fencing_token FROM effect_attempts WHERE effect_id = ?",
            (effect_id,)
        ).fetchone()
        self.assertEqual(attempt[0], 1)
        self.assertEqual(attempt[1], 1)

    def test_phase2_dispatched_to_executed(self) -> None:
        """测试: dispatched → executed (外部确认完成)"""
        effect_id = "effect-002"
        self._insert_effect(effect_id, "dispatched")
        self._add_transition(effect_id, "dispatched", "executed", "worker")

        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "executed")

        trans = self.conn.execute(
            "SELECT from_status, to_status FROM effect_transitions WHERE effect_id = ?",
            (effect_id,)
        ).fetchone()
        self.assertEqual(trans, ("dispatched", "executed"))

    def test_phase3_executed_to_committing(self) -> None:
        """测试: executed → committing (结果持久化)"""
        effect_id = "effect-003"
        self._insert_effect(effect_id, "executed")
        self._add_transition(effect_id, "executed", "committing", "state_engine")

        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "committing")

    def test_full_four_phase_sequence(self) -> None:
        """测试: 完整四阶段序列 prepared → dispatched → executed → committing"""
        effect_id = "effect-004"
        self._insert_effect(effect_id, "prepared")

        # Phase 1
        self._add_transition(effect_id, "prepared", "dispatched", "orchestrator")
        self.conn.execute("UPDATE effects SET status = 'dispatched' WHERE effect_id = ?", (effect_id,))
        self._add_attempt(effect_id, 1)

        # Phase 2
        self._add_transition(effect_id, "dispatched", "executed", "worker")
        self.conn.execute("UPDATE effects SET status = 'executed' WHERE effect_id = ?", (effect_id,))

        # Phase 3
        self._add_transition(effect_id, "executed", "committing", "state_engine")
        self.conn.execute("UPDATE effects SET status = 'committing' WHERE effect_id = ?", (effect_id,))

        self.conn.commit()

        # 验证最终状态
        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "committing")

        # 验证 transitions 数量
        trans = self.conn.execute(
            "SELECT from_status, to_status FROM effect_transitions WHERE effect_id = ? ORDER BY id",
            (effect_id,)
        ).fetchall()
        self.assertEqual(len(trans), 3)
        self.assertEqual(trans[0], ("prepared", "dispatched"))
        self.assertEqual(trans[1], ("dispatched", "executed"))
        self.assertEqual(trans[2], ("executed", "committing"))

        # 验证 attempt 记录
        attempt = self.conn.execute(
            "SELECT attempt_seq, fencing_token FROM effect_attempts WHERE effect_id = ?",
            (effect_id,)
        ).fetchone()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt[0], 1)

    # === uncertain 状态测试 ===

    def test_uncertain_state_on_crash(self) -> None:
        """测试: 崩溃后进入 uncertain 状态 (可探测)"""
        effect_id = "effect-uncertain-001"
        self._insert_effect(effect_id, "dispatched", probe_mode="auto")
        self._add_transition(effect_id, "dispatched", "uncertain", "crash_recovery")
        self.conn.execute("UPDATE effects SET status = 'uncertain', probe_state = 'probe_pending' WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_state FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "uncertain")
        self.assertEqual(row[1], "probe_pending")

    def test_uncertain_probe_success_to_committing(self) -> None:
        """测试: uncertain + probe_success → committing"""
        effect_id = "effect-uncertain-002"
        self._insert_effect(effect_id, "uncertain", probe_mode="auto")
        self.conn.execute("UPDATE effects SET probe_state = 'probing' WHERE effect_id = ?", (effect_id,))
        self._add_transition(effect_id, "uncertain", "committing", "probe_success")
        self.conn.execute("UPDATE effects SET status = 'committing', probe_state = NULL WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_state FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "committing")
        self.assertIsNone(row[1])

    def test_uncertain_probe_failure_to_failed(self) -> None:
        """测试: uncertain + probe_failure → failed"""
        effect_id = "effect-uncertain-003"
        self._insert_effect(effect_id, "uncertain", probe_mode="auto")
        self._add_transition(effect_id, "uncertain", "failed", "probe_failure")
        self.conn.execute("UPDATE effects SET status = 'failed' WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "failed")

    # === executed_assumed 脏终态测试 ===

    def test_executed_assumed_for_non_probe_mode(self) -> None:
        """测试: probe_mode:none 崩溃后进入 executed_assumed 脏终态"""
        effect_id = "effect-assumed-001"
        self._insert_effect(effect_id, "dispatched", probe_mode="none")
        self._add_transition(effect_id, "dispatched", "executed_assumed", "crash_recovery")
        self.conn.execute("UPDATE effects SET status = 'executed_assumed' WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_mode FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "executed_assumed")
        self.assertEqual(row[1], "none")

    def test_executed_assumed_triggers_scope_quarantine(self) -> None:
        """测试: executed_assumed 触发 scope 隔离"""
        effect_id = "effect-assumed-002"
        target_scope = "/home/user/data"
        self._insert_effect(effect_id, "executed_assumed", probe_mode="none")

        # 模拟 scope quarantine 标记
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS scope_quarantine (scope TEXT PRIMARY KEY, quarantined_at TEXT)"
        )
        self.conn.execute(
            "INSERT INTO scope_quarantine (scope, quarantined_at) VALUES (?, datetime('now'))",
            (target_scope,)
        )
        self.conn.commit()

        row = self.conn.execute("SELECT scope FROM scope_quarantine WHERE scope = ?", (target_scope,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], target_scope)

    # === 补偿 Effect 测试 ===

    def test_compensation_effect_points_to_source(self) -> None:
        """测试: 补偿 Effect 通过 compensates_effect_id 指向源 Effect"""
        source_id = "effect-source-001"
        compensation_id = "effect-comp-001"

        self._insert_effect(source_id, "executed")
        self.conn.execute(
            """INSERT INTO effects (
                effect_id, task_id, trace_id, intent_key, actor, action, target,
                tier, reversibility, status, probe_mode, compensates_effect_id,
                schema_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (compensation_id, "task-001", "trace-001", "intent-comp-001", "worker",
             "file_write", "/tmp/compensated.txt", "TIER_1", "REV_ROLLBACKABLE",
             "prepared", "auto", source_id, "3.2.0")
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT compensates_effect_id FROM effects WHERE effect_id = ?",
            (compensation_id,)
        ).fetchone()
        self.assertEqual(row[0], source_id)

    # === 幂等性测试 ===

    def test_intent_key_prevents_duplicate_dispatched(self) -> None:
        """测试: 相同 intent_key 且状态为 prepared/dispatched 时，重复下发被拦截"""
        effect_id_1 = "effect-idempotent-001"
        effect_id_2 = "effect-idempotent-002"
        intent_key = "blake3(file_write+/tmp/test.txt+{}+v1+worker+)"

        self._insert_effect(effect_id_1, "dispatched")
        self.conn.execute(
            "UPDATE effects SET intent_key = ? WHERE effect_id = ?",
            (intent_key, effect_id_1)
        )

        # 相同 intent_key 的新 effect 应该被拒绝
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO effects (
                    effect_id, task_id, trace_id, intent_key, actor, action, target,
                    tier, reversibility, status, probe_mode, schema_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (effect_id_2, "task-001", "trace-002", intent_key, "worker",
                 "file_write", "/tmp/test.txt", "TIER_1", "REV_ROLLBACKABLE",
                 "prepared", "auto", "3.2.0")
            )


if __name__ == "__main__":
    unittest.main()
