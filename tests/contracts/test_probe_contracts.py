from __future__ import annotations

import unittest
import tempfile
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta


class ProbeContractsTest(unittest.TestCase):
    """测试探针 (probe) 协议

    协议要求 (来自 specs/probes/*.json 和 worker_lifecycle.json):
    1. uncertain 状态后进入 probing 子状态
    2. probe 有独立 schema: probe_id, probe_type, target, expected_state
    3. probe_result: success (实际状态匹配预期) 或 failure (不匹配)
    4. probe 超时后标记为失败
    5. probe_mode:none 跳过探测，直接进入 executed_assumed
    """

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript("""
            CREATE TABLE effects (
                effect_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                probe_mode TEXT DEFAULT 'auto',
                probe_state TEXT,
                probe_id TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE probes (
                probe_id TEXT PRIMARY KEY,
                effect_id TEXT NOT NULL,
                probe_type TEXT NOT NULL,
                target TEXT NOT NULL,
                expected_state TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                result TEXT,
                error_message TEXT,
                FOREIGN KEY (effect_id) REFERENCES effects(effect_id)
            );

            CREATE TABLE effect_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                effect_id TEXT NOT NULL,
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

    def _insert_effect(self, effect_id: str, status: str, probe_mode: str = "auto") -> None:
        self.conn.execute(
            "INSERT INTO effects (effect_id, status, probe_mode, updated_at) VALUES (?, ?, ?, datetime('now'))",
            (effect_id, status, probe_mode)
        )
        self.conn.commit()

    def _add_transition(self, effect_id: str, from_status: str, to_status: str, triggered_by: str) -> None:
        self.conn.execute(
            "INSERT INTO effect_transitions (effect_id, from_status, to_status, at, triggered_by) VALUES (?, ?, ?, datetime('now'), ?)",
            (effect_id, from_status, to_status, triggered_by)
        )
        self.conn.commit()

    def _add_probe(self, probe_id: str, effect_id: str, probe_type: str, target: str) -> None:
        self.conn.execute(
            "INSERT INTO probes (probe_id, effect_id, probe_type, target, started_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (probe_id, effect_id, probe_type, target)
        )
        self.conn.commit()

    # === 核心探针测试 ===

    def test_uncertain_to_probing_transition(self) -> None:
        """测试: uncertain 状态后进入 probing 子状态"""
        effect_id = "probe-effect-001"
        self._insert_effect(effect_id, "uncertain")

        # 模拟进入 probing
        self.conn.execute(
            "UPDATE effects SET probe_state = 'probing', probe_id = 'probe-001' WHERE effect_id = ?",
            (effect_id,)
        )
        self._add_transition(effect_id, "uncertain", "probing", "recovery")
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_state FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "uncertain")
        self.assertEqual(row[1], "probing")

    def test_probe_schema_has_required_fields(self) -> None:
        """测试: probe schema 包含必要字段 (符合 specs/probes/*.json)"""
        effect_id = "probe-effect-002"
        probe_id = "probe-002"
        self._insert_effect(effect_id, "uncertain")
        self._add_probe(probe_id, effect_id, "file_exists", "/tmp/test.txt")

        row = self.conn.execute(
            "SELECT probe_id, probe_type, target FROM probes WHERE probe_id = ?",
            (probe_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], probe_id)
        self.assertEqual(row[1], "file_exists")
        self.assertEqual(row[2], "/tmp/test.txt")

    def test_probe_success_to_committing(self) -> None:
        """测试: probe 成功 → committing"""
        effect_id = "probe-effect-003"
        probe_id = "probe-003"
        self._insert_effect(effect_id, "uncertain")
        self.conn.execute("UPDATE effects SET probe_state = 'probing', probe_id = ? WHERE effect_id = ?", (probe_id, effect_id))
        self._add_probe(probe_id, effect_id, "file_exists", "/tmp/test.txt")

        # probe 成功
        self.conn.execute(
            "UPDATE probes SET completed_at = datetime('now'), result = 'success' WHERE probe_id = ?",
            (probe_id,)
        )
        self.conn.execute("UPDATE effects SET status = 'committing', probe_state = NULL WHERE effect_id = ?", (effect_id,))
        self._add_transition(effect_id, "uncertain", "committing", "probe_success")
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_state FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "committing")
        self.assertIsNone(row[1])

        probe_row = self.conn.execute("SELECT result FROM probes WHERE probe_id = ?", (probe_id,)).fetchone()
        self.assertEqual(probe_row[0], "success")

    def test_probe_failure_to_failed(self) -> None:
        """测试: probe 失败 → failed"""
        effect_id = "probe-effect-004"
        probe_id = "probe-004"
        self._insert_effect(effect_id, "uncertain")
        self.conn.execute("UPDATE effects SET probe_state = 'probing', probe_id = ? WHERE effect_id = ?", (probe_id, effect_id))
        self._add_probe(probe_id, effect_id, "file_exists", "/tmp/missing.txt")

        # probe 失败
        self.conn.execute(
            "UPDATE probes SET completed_at = datetime('now'), result = 'failure', error_message = 'file not found' WHERE probe_id = ?",
            (probe_id,)
        )
        self.conn.execute("UPDATE effects SET status = 'failed', probe_state = 'probe_failed' WHERE effect_id = ?", (effect_id,))
        self._add_transition(effect_id, "uncertain", "failed", "probe_failure")
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_state FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertEqual(row[1], "probe_failed")

        probe_row = self.conn.execute("SELECT result, error_message FROM probes WHERE probe_id = ?", (probe_id,)).fetchone()
        self.assertEqual(probe_row[0], "failure")
        self.assertEqual(probe_row[1], "file not found")

    def test_probe_timeout_handling(self) -> None:
        """测试: probe 超时 → 标记失败"""
        effect_id = "probe-effect-005"
        probe_id = "probe-005"
        self._insert_effect(effect_id, "uncertain")
        self.conn.execute("UPDATE effects SET probe_state = 'probing', probe_id = ? WHERE effect_id = ?", (probe_id, effect_id))
        self._add_probe(probe_id, effect_id, "network_check", "https://api.example.com")

        # 模拟超时 (started_at 设置为 10 秒前)
        timeout_time = (datetime.now() - timedelta(seconds=11)).isoformat()
        self.conn.execute(
            "UPDATE probes SET started_at = ? WHERE probe_id = ?",
            (timeout_time, probe_id)
        )
        self.conn.execute(
            "UPDATE probes SET completed_at = datetime('now'), result = 'failure', error_message = 'timeout' WHERE probe_id = ?",
            (probe_id,)
        )
        self.conn.execute("UPDATE effects SET status = 'failed', probe_state = 'probe_failed' WHERE effect_id = ?", (effect_id,))
        self.conn.commit()

        row = self.conn.execute("SELECT status FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "failed")

    def test_probe_mode_none_skips_probe(self) -> None:
        """测试: probe_mode:none 跳过探测，直接进入 executed_assumed"""
        effect_id = "probe-effect-006"
        self._insert_effect(effect_id, "dispatched", probe_mode="none")

        # 模拟崩溃恢复: 跳过探测，直接进入 executed_assumed
        self.conn.execute("UPDATE effects SET status = 'executed_assumed' WHERE effect_id = ?", (effect_id,))
        self._add_transition(effect_id, "dispatched", "executed_assumed", "crash_recovery")
        self.conn.commit()

        row = self.conn.execute("SELECT status, probe_mode FROM effects WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(row[0], "executed_assumed")
        self.assertEqual(row[1], "none")

        # 确保没有 probe 记录
        probe_row = self.conn.execute("SELECT COUNT(*) FROM probes WHERE effect_id = ?", (effect_id,)).fetchone()
        self.assertEqual(probe_row[0], 0)

    # === probe spec 文件验证 ===

    def test_probe_spec_files_exist(self) -> None:
        """测试: probe spec 文件存在 (specs/probes/)"""
        from pathlib import Path
        repo_root = Path(__file__).parent.parent.parent

        probe_files = [
            repo_root / "specs" / "probes" / "file_write.json",
            repo_root / "specs" / "probes" / "file_delete.json",
            repo_root / "specs" / "probes" / "network_request.json",
        ]

        for pf in probe_files:
            self.assertTrue(pf.exists(), f"Probe spec missing: {pf}")

    def test_probe_spec_valid_json(self) -> None:
        """测试: probe spec 是有效 JSON"""
        from pathlib import Path
        import json
        repo_root = Path(__file__).parent.parent.parent

        probe_specs = [
            repo_root / "specs" / "probes" / "file_write.json",
            repo_root / "specs" / "probes" / "file_delete.json",
        ]

        for spec_path in probe_specs:
            with open(spec_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    self.assertIn("probe_type", data)
                    self.assertIn("target_pattern", data)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {spec_path}: {e}")


class ProbeStateMachineTest(unittest.TestCase):
    """测试探针状态机与 worker_lifecycle 集成"""

    def test_worker_lifecycle_has_probe_transitions(self) -> None:
        """测试: worker_lifecycle.json 包含探针相关转移"""
        from pathlib import Path
        import json

        repo_root = Path(__file__).parent.parent.parent
        lifecycle_path = repo_root / "specs" / "state-machines" / "worker_lifecycle.json"

        with open(lifecycle_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        transitions = data.get("transitions", [])
        event_ids = [t["event_id"] for t in transitions]

        self.assertIn("EV_PROBE_SUCCESS", event_ids)
        self.assertIn("EV_PROBE_FAILURE", event_ids)
        self.assertIn("EV_PROBE_ASSUMED", event_ids)

    def test_effect_ledger_has_probe_fields(self) -> None:
        """测试: effect_ledger.json 包含探针字段"""
        from pathlib import Path
        import json

        repo_root = Path(__file__).parent.parent.parent
        ledger_path = repo_root / "specs" / "schemas" / "effect_ledger.json"

        with open(ledger_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        props = data.get("properties", {})
        self.assertIn("probe_mode", props)
        self.assertIn("probe_state", props)

        probe_mode_enum = props["probe_mode"]["enum"]
        self.assertIn("auto", probe_mode_enum)
        self.assertIn("none", probe_mode_enum)


if __name__ == "__main__":
    unittest.main()
