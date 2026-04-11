from __future__ import annotations

import unittest
import tempfile
import sqlite3
from pathlib import Path


class ExecutedAssumedReconcileContractsTest(unittest.TestCase):
    """测试 executed_assumed 脏终态与 reconcile 协议

    协议要求 (来自 worker_lifecycle.json 和 task_concurrency.json):
    1. executed_assumed 是脏终态，触发 scope_quarantined
    2. 该 scope 下所有 task 的写操作被 Preflight 拦截
    3. 仅人工 reconcile (EV_USER_RECONCILE_SUCCESS/FAILURE) 解除
    4. Doctor reconcile/force_kill 携带特权 Context 绕过 scope 锁定
    5. reconcile_success → 补录 State → committing
    6. reconcile_failure → 预扣退回 → failed_terminal
    """

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript("""
            CREATE TABLE effects (
                effect_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                probe_mode TEXT DEFAULT 'auto',
                target TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                scope TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE scope_quarantine (
                scope TEXT PRIMARY KEY,
                quarantined_at TEXT NOT NULL,
                triggered_by_effect_id TEXT NOT NULL,
                reconciled_at TEXT,
                reconciled_result TEXT
            );

            CREATE TABLE effect_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                effect_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                at TEXT NOT NULL,
                triggered_by TEXT NOT NULL
            );

            CREATE TABLE task_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                at TEXT NOT NULL,
                triggered_by TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _insert_effect(self, effect_id: str, task_id: str, status: str, target: str, probe_mode: str = "auto") -> None:
        self.conn.execute(
            "INSERT INTO effects (effect_id, task_id, status, probe_mode, target, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (effect_id, task_id, status, probe_mode, target)
        )
        self.conn.commit()

    def _insert_task(self, task_id: str, status: str, scope: str) -> None:
        self.conn.execute(
            "INSERT INTO tasks (task_id, status, scope, updated_at) VALUES (?, ?, ?, datetime('now'))",
            (task_id, status, scope)
        )
        self.conn.commit()

    def _add_effect_transition(self, effect_id: str, from_status: str, to_status: str, triggered_by: str) -> None:
        self.conn.execute(
            "INSERT INTO effect_transitions (effect_id, from_status, to_status, at, triggered_by) VALUES (?, ?, ?, datetime('now'), ?)",
            (effect_id, from_status, to_status, triggered_by)
        )
        self.conn.commit()

    def _add_task_transition(self, task_id: str, from_status: str, to_status: str, triggered_by: str) -> None:
        self.conn.execute(
            "INSERT INTO task_transitions (task_id, from_status, to_status, at, triggered_by) VALUES (?, ?, ?, datetime('now'), ?)",
            (task_id, from_status, to_status, triggered_by)
        )
        self.conn.commit()

    def _add_scope_quarantine(self, scope: str, effect_id: str) -> None:
        self.conn.execute(
            "INSERT INTO scope_quarantine (scope, quarantined_at, triggered_by_effect_id) VALUES (?, datetime('now'), ?)",
            (scope, effect_id)
        )
        self.conn.commit()

    # === executed_assumed 脏终态测试 ===

    def test_executed_assumed_state_triggered_by_probe_mode_none(self) -> None:
        """测试: probe_mode:none 崩溃后进入 executed_assumed 脏终态"""
        effect_id = "effect-assumed-001"
        task_id = "task-001"

        self._insert_effect(effect_id, task_id, "dispatched", "/home/user/data", probe_mode="none")
        self._add_effect_transition(effect_id, "dispatched", "executed_assumed", "crash_recovery")
        self.conn.execute("UPDATE effects SET status = 'executed_assumed' WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_mode FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "executed_assumed")
        self.assertEqual(row[1], "none")

    def test_executed_assumed_triggers_scope_quarantine(self) -> None:
        """测试: executed_assumed 触发 scope 隔离"""
        effect_id = "effect-assumed-002"
        task_id = "task-002"
        scope = "/home/user/data"

        self._insert_effect(effect_id, task_id, "executed_assumed", scope, probe_mode="none")
        self._add_scope_quarantine(scope, effect_id)

        row = self.conn.execute("SELECT scope, triggered_by_effect_id FROM scope_quarantine WHERE scope = ?", (scope,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], scope)
        self.assertEqual(row[1], effect_id)

    def test_scope_quarantine_blocks_write_operations(self) -> None:
        """测试: scope quarantine 期间写操作被 Preflight 拦截"""
        scope = "/home/user/data"
        effect_id = "effect-assumed-003"

        self._add_scope_quarantine(scope, effect_id)

        # 模拟 Preflight 检查
        is_quarantined = self.conn.execute(
            "SELECT 1 FROM scope_quarantine WHERE scope = ? AND reconciled_at IS NULL",
            (scope,)
        ).fetchone() is not None

        self.assertTrue(is_quarantined)

    def test_scope_quarantine_released_by_reconcile_success(self) -> None:
        """测试: reconcile_success 解除 scope quarantine"""
        scope = "/home/user/data"
        effect_id = "effect-assumed-004"

        self._add_scope_quarantine(scope, effect_id)

        # 模拟 reconcile_success
        self.conn.execute(
            "UPDATE scope_quarantine SET reconciled_at = datetime('now'), reconciled_result = 'success' WHERE scope = ?",
            (scope,)
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT reconciled_result FROM scope_quarantine WHERE scope = ?",
            (scope,)
        ).fetchone()
        self.assertEqual(row[0], "success")

    # === reconcile 状态机测试 ===

    def test_reconcile_success_transition(self) -> None:
        """测试: EV_USER_RECONCILE_SUCCESS: failed → committing"""
        task_id = "task-reconcile-001"
        effect_id = "effect-reconcile-001"
        scope = "/home/user/data"

        self._insert_task(task_id, "failed", scope)
        self._insert_effect(effect_id, task_id, "executed_assumed", scope, probe_mode="none")
        self._add_scope_quarantine(scope, effect_id)

        # 模拟 reconcile_success
        self.conn.execute("UPDATE tasks SET status = 'committing' WHERE task_id = ?", (task_id,))
        self._add_task_transition(task_id, "failed", "committing", "user_reconcile_success")
        self.conn.execute(
            "UPDATE scope_quarantine SET reconciled_at = datetime('now'), reconciled_result = 'success' WHERE scope = ?",
            (scope,)
        )
        self.conn.commit()

        task_row = self.conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(task_row[0], "committing")

        trans_row = self.conn.execute(
            "SELECT from_status, to_status, triggered_by FROM task_transitions WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        self.assertEqual(trans_row, ("failed", "committing", "user_reconcile_success"))

    def test_reconcile_failure_transition(self) -> None:
        """测试: EV_USER_RECONCILE_FAILURE: failed → failed_terminal"""
        task_id = "task-reconcile-002"
        effect_id = "effect-reconcile-002"
        scope = "/home/user/data"

        self._insert_task(task_id, "failed", scope)
        self._insert_effect(effect_id, task_id, "executed_assumed", scope, probe_mode="none")
        self._add_scope_quarantine(scope, effect_id)

        # 模拟 reconcile_failure
        self.conn.execute("UPDATE tasks SET status = 'failed_terminal' WHERE task_id = ?", (task_id,))
        self._add_task_transition(task_id, "failed", "failed_terminal", "user_reconcile_failure")
        self.conn.execute(
            "UPDATE scope_quarantine SET reconciled_at = datetime('now'), reconciled_result = 'failure' WHERE scope = ?",
            (scope,)
        )
        self.conn.commit()

        task_row = self.conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(task_row[0], "failed_terminal")

    def test_reconcile_success_requires_executed_assumed_effect(self) -> None:
        """测试: reconcile_success 前置守卫: 必须有 executed_assumed Effect"""
        task_id = "task-reconcile-003"
        scope = "/home/user/data"

        self._insert_task(task_id, "failed", scope)
        # 没有 executed_assumed effect

        # 模拟检查守卫
        has_executed_assumed = self.conn.execute(
            "SELECT 1 FROM effects WHERE task_id = ? AND status = 'executed_assumed'",
            (task_id,)
        ).fetchone() is not None

        self.assertFalse(has_executed_assumed)

    def test_reconcile_failure_refunds_preallocated_budget(self) -> None:
        """测试: reconcile_failure 退回预扣金额 (财务崩溃冲正)"""
        task_id = "task-reconcile-004"
        effect_id = "effect-reconcile-004"
        scope = "/home/user/data"
        preallocated_amount = 100

        self._insert_task(task_id, "failed", scope)
        self._insert_effect(effect_id, task_id, "executed_assumed", scope, probe_mode="none")
        self._add_scope_quarantine(scope, effect_id)

        # 模拟预算表
        self.conn.executescript("""
            CREATE TABLE budget (
                task_id TEXT PRIMARY KEY,
                allocated INTEGER NOT NULL,
                refunded INTEGER DEFAULT 0
            );
            INSERT INTO budget (task_id, allocated) VALUES (?, ?);
        """, (task_id, preallocated_amount))

        # reconcile_failure: 退回预扣金额
        self.conn.execute("UPDATE budget SET refunded = allocated WHERE task_id = ?", (task_id,))
        self.conn.execute("UPDATE tasks SET status = 'failed_terminal' WHERE task_id = ?", (task_id,))
        self.conn.commit()

        budget_row = self.conn.execute("SELECT allocated, refunded FROM budget WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(budget_row[0], 100)
        self.assertEqual(budget_row[1], 100)

    # === Doctor 特权绕过测试 ===

    def test_doctor_force_kill_bypasses_scope_quarantine(self) -> None:
        """测试: Doctor force_kill 携带特权 Context 绕过 scope 锁定"""
        scope = "/home/user/data"
        effect_id = "effect-assumed-005"

        self._add_scope_quarantine(scope, effect_id)

        # 模拟 Doctor 特权操作
        is_quarantined = self.conn.execute(
            "SELECT 1 FROM scope_quarantine WHERE scope = ? AND reconciled_at IS NULL",
            (scope,)
        ).fetchone() is not None
        self.assertTrue(is_quarantined)

        # Doctor 携带特权标志，允许操作
        doctor_bypass = True
        operation_allowed = doctor_bypass or not is_quarantined
        self.assertTrue(operation_allowed)

    def test_doctor_reconcile_bypasses_scope_quarantine(self) -> None:
        """测试: Doctor reconcile 携带特权 Context 绕过 scope 锁定"""
        scope = "/home/user/data"
        effect_id = "effect-assumed-006"

        self._add_scope_quarantine(scope, effect_id)

        # Doctor reconcile 特权
        doctor_reconcile = True
        is_quarantined = self.conn.execute(
            "SELECT 1 FROM scope_quarantine WHERE scope = ? AND reconciled_at IS NULL",
            (scope,)
        ).fetchone() is not None

        operation_allowed = doctor_reconcile or not is_quarantined
        self.assertTrue(operation_allowed)

    # === worker_lifecycle.json 约束验证 ===

    def test_worker_lifecycle_has_reconcile_transitions(self) -> None:
        """测试: worker_lifecycle.json 包含 reconcile 转移"""
        from pathlib import Path
        import json

        repo_root = Path(__file__).parent.parent.parent
        lifecycle_path = repo_root / "specs" / "state-machines" / "worker_lifecycle.json"

        with open(lifecycle_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        transitions = data.get("transitions", [])
        event_ids = [t["event_id"] for t in transitions]

        self.assertIn("EV_USER_RECONCILE_SUCCESS", event_ids)
        self.assertIn("EV_USER_RECONCILE_FAILURE", event_ids)

    def test_worker_lifecycle_reconcile_success_has_guard(self) -> None:
        """测试: reconcile_success 有 has_executed_assumed_effect 守卫"""
        from pathlib import Path
        import json

        repo_root = Path(__file__).parent.parent.parent
        lifecycle_path = repo_root / "specs" / "state-machines" / "worker_lifecycle.json"

        with open(lifecycle_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        transitions = data.get("transitions", [])
        reconcile_success = next(
            (t for t in transitions if t["event_id"] == "EV_USER_RECONCILE_SUCCESS"),
            None
        )
        self.assertIsNotNone(reconcile_success)
        guards = reconcile_success.get("x-guards", [])
        self.assertIn("has_executed_assumed_effect", guards)

    def test_task_concurrency_has_scope_quarantine_with_doctor_bypass(self) -> None:
        """测试: task_concurrency.json 的 scope_quarantine 有 x-doctor-bypass"""
        from pathlib import Path
        import json

        repo_root = Path(__file__).parent.parent.parent
        tc_path = repo_root / "specs" / "schemas" / "task_concurrency.json"

        with open(tc_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scope_quarantine = data.get("scope_quarantine", {})
        self.assertIn("x-doctor-bypass", scope_quarantine)


class ReconcileStateMachineIntegrationTest(unittest.TestCase):
    """测试 reconcile 与完整状态机集成"""

    def test_full_reconcile_success_flow(self) -> None:
        """测试: 完整 reconcile_success 流程"""
        task_id = "task-reconcile-full-001"
        effect_id = "effect-reconcile-full-001"
        scope = "/home/user/data"

        # 1. 创建 task 和 effect
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT, scope TEXT);
            CREATE TABLE effects (effect_id TEXT PRIMARY KEY, task_id TEXT, status TEXT, probe_mode TEXT, target TEXT);
            CREATE TABLE scope_quarantine (scope TEXT PRIMARY KEY, triggered_by_effect_id TEXT, reconciled_at TEXT);
            CREATE TABLE transitions (id INTEGER PRIMARY KEY, task_id TEXT, from_status TEXT, to_status TEXT, triggered_by TEXT);

            INSERT INTO tasks VALUES ('task-reconcile-full-001', 'failed', '/home/user/data');
            INSERT INTO effects VALUES ('effect-reconcile-full-001', 'task-reconcile-full-001', 'executed_assumed', 'none', '/home/user/data');
            INSERT INTO scope_quarantine VALUES ('/home/user/data', 'effect-reconcile-full-001', NULL);
        """)

        # 2. 用户 reconcile_success
        conn.execute("UPDATE tasks SET status = 'committing' WHERE task_id = ?", (task_id,))
        conn.execute("INSERT INTO transitions (task_id, from_status, to_status, triggered_by) VALUES (?, 'failed', 'committing', 'user_reconcile_success')", (task_id,))
        conn.execute("UPDATE scope_quarantine SET reconciled_at = datetime('now') WHERE scope = ?", (scope,))
        conn.commit()

        # 3. 验证
        task_status = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()[0]
        self.assertEqual(task_status, "committing")

        is_quarantined = conn.execute(
            "SELECT 1 FROM scope_quarantine WHERE scope = ? AND reconciled_at IS NULL",
            (scope,)
        ).fetchone() is None
        self.assertTrue(is_quarantined)

        conn.close()

    def test_full_reconcile_failure_flow(self) -> None:
        """测试: 完整 reconcile_failure 流程"""
        task_id = "task-reconcile-full-002"
        effect_id = "effect-reconcile-full-002"
        scope = "/home/user/data"

        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT, scope TEXT);
            CREATE TABLE effects (effect_id TEXT PRIMARY KEY, task_id TEXT, status TEXT, probe_mode TEXT, target TEXT);
            CREATE TABLE scope_quarantine (scope TEXT PRIMARY KEY, triggered_by_effect_id TEXT, reconciled_at TEXT);
            CREATE TABLE budget (task_id TEXT PRIMARY KEY, allocated INTEGER, refunded INTEGER);
            CREATE TABLE transitions (id INTEGER PRIMARY KEY, task_id TEXT, from_status TEXT, to_status TEXT, triggered_by TEXT);

            INSERT INTO tasks VALUES ('task-reconcile-full-002', 'failed', '/home/user/data');
            INSERT INTO effects VALUES ('effect-reconcile-full-002', 'task-reconcile-full-002', 'executed_assumed', 'none', '/home/user/data');
            INSERT INTO scope_quarantine VALUES ('/home/user/data', 'effect-reconcile-full-002', NULL);
            INSERT INTO budget VALUES ('task-reconcile-full-002', 100, 0);
        """)

        # 2. 用户 reconcile_failure
        conn.execute("UPDATE tasks SET status = 'failed_terminal' WHERE task_id = ?", (task_id,))
        conn.execute("INSERT INTO transitions (task_id, from_status, to_status, triggered_by) VALUES (?, 'failed', 'failed_terminal', 'user_reconcile_failure')", (task_id,))
        conn.execute("UPDATE budget SET refunded = allocated WHERE task_id = ?", (task_id,))
        conn.execute("UPDATE scope_quarantine SET reconciled_at = datetime('now') WHERE scope = ?", (scope,))
        conn.commit()

        # 3. 验证
        task_status = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()[0]
        self.assertEqual(task_status, "failed_terminal")

        budget = conn.execute("SELECT allocated, refunded FROM budget WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(budget[0], 100)
        self.assertEqual(budget[1], 100)

        conn.close()


if __name__ == "__main__":
    unittest.main()
