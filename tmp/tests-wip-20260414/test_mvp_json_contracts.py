from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import ExitStack, contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

import tools.mvp.safeclaw_mvp as safeclaw_mvp
from tools.checks.smoke_utils import json_assertions as smoke_json_assertions


def capture_json_call(handler, args: list[str]) -> tuple[int, dict[str, object]]:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = handler(args)
    return exit_code, json.loads(stdout.getvalue())


@contextmanager
def patched_state_root() -> dict[str, Path]:
    with tempfile.TemporaryDirectory() as temp_dir, ExitStack() as stack:
        repo_root = Path(temp_dir)
        state_root = repo_root / "target" / "mvp"
        session_file = state_root / "last_session.json"
        workspace_file = state_root / "workspace.json"
        workspace_root = state_root / "workspaces"
        default_db = state_root / "session.db"
        default_output = state_root / "output.txt"

        state_root.mkdir(parents=True, exist_ok=True)

        for name, value in {
            "REPO_ROOT": repo_root,
            "STATE_ROOT": state_root,
            "SESSION_FILE": session_file,
            "WORKSPACE_FILE": workspace_file,
            "WORKSPACE_ROOT": workspace_root,
            "DEFAULT_DB": default_db,
            "DEFAULT_OUTPUT": default_output,
        }.items():
            stack.enter_context(mock.patch.object(safeclaw_mvp, name, value))

        yield {
            "repo_root": repo_root,
            "state_root": state_root,
            "session_file": session_file,
            "workspace_file": workspace_file,
            "workspace_root": workspace_root,
            "default_db": default_db,
            "default_output": default_output,
        }


class MvpJsonContractsTest(unittest.TestCase):
    def test_doctor_json_matches_smoke_assertion_contract(self) -> None:
        errors: list[str] = []

        with patched_state_root() as paths:
            repo_root = paths["repo_root"]
            entry_dir = repo_root / "tools" / "mvp"
            entry_dir.mkdir(parents=True, exist_ok=True)
            entrypoints = []
            for suffix in ("cmd", "ps1", "py"):
                entry_path = entry_dir / f"safeclaw_mvp.{suffix}"
                entry_path.write_text("stub", encoding="utf-8")
                entrypoints.append((suffix, entry_path))

            linker_path = repo_root / "toolchain" / "linker.exe"
            linker_path.parent.mkdir(parents=True, exist_ok=True)
            linker_path.write_text("stub", encoding="utf-8")
            paths["default_db"].write_text("", encoding="utf-8")
            paths["default_output"].write_text("", encoding="utf-8")

            with mock.patch.object(
                safeclaw_mvp,
                "ENTRYPOINT_FILES",
                tuple(entrypoints),
            ), mock.patch.object(
                safeclaw_mvp,
                "LINKER",
                str(linker_path),
            ), mock.patch.object(
                safeclaw_mvp,
                "build_rust_env",
                return_value=({}, "cargo.exe", "rustc.exe"),
            ), mock.patch.object(
                safeclaw_mvp,
                "probe_command",
                side_effect=[(True, "cargo 1.85.0"), (True, "rustc 1.85.0")],
            ), mock.patch.object(
                safeclaw_mvp,
                "build_runtime_profile_payload",
                return_value={
                    "mode": "local_mvp",
                    "offline_ready": True,
                    "llm_required": False,
                    "sidecar_required": False,
                },
            ), mock.patch.object(
                safeclaw_mvp,
                "build_model_provider_payload",
                return_value={
                    "configured": False,
                    "required": False,
                    "status": "not-configured",
                    "degradation_mode": "local_only_ok",
                    "detail": "offline local mode",
                },
            ), mock.patch.object(
                safeclaw_mvp,
                "build_sidecar_payload",
                return_value={
                    "configured": False,
                    "required": False,
                    "status": "not-configured",
                    "detail": "offline local mode",
                },
            ):
                exit_code, payload = capture_json_call(
                    safeclaw_mvp.run_doctor,
                    ["--json"],
                )

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "doctor")
        self.assertEqual(payload["schema_version"], "mvp-wrapper.v1")

        result = smoke_json_assertions.extract_json_result(
            payload,
            errors,
            "doctor-json",
            "doctor",
        )
        smoke_json_assertions.assert_doctor_json_result(
            result,
            errors,
            "doctor-json",
            expected_db_path=r"target\mvp\session.db",
            expected_output_path=r"target\mvp\output.txt",
            expected_db_source="default",
            expected_output_source="default",
            expected_workspace_active=False,
        )

        self.assertEqual(errors, [])

    def test_workspace_json_matches_default_activate_and_clear_contracts(self) -> None:
        errors: list[str] = []

        with patched_state_root():
            exit_code, payload = capture_json_call(safeclaw_mvp.run_workspace, ["--json"])
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "workspace-default-json",
                "workspace",
            )
            smoke_json_assertions.assert_workspace_json_result(
                result,
                errors,
                "workspace-default-json",
                expected_active=False,
                expected_name=None,
                expected_db_path=r"target\mvp\session.db",
                expected_output_path=r"target\mvp\output.txt",
            )

            exit_code, payload = capture_json_call(
                safeclaw_mvp.run_workspace,
                ["--name", "demo", "--json"],
            )
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "workspace-activate-json",
                "workspace",
            )
            smoke_json_assertions.assert_workspace_json_result(
                result,
                errors,
                "workspace-activate-json",
                expected_active=True,
                expected_name="demo",
                expected_db_path=r"target\mvp\workspaces\demo\session.db",
                expected_output_path=r"target\mvp\workspaces\demo\output.txt",
                expected_changed=True,
            )

            exit_code, payload = capture_json_call(
                safeclaw_mvp.run_workspace,
                ["--clear", "--json"],
            )
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "workspace-clear-json",
                "workspace",
            )
            smoke_json_assertions.assert_workspace_clear_json_result(
                result,
                errors,
                "workspace-clear-json",
            )

            exit_code, payload = capture_json_call(
                safeclaw_mvp.run_workspace,
                ["--clear", "--json"],
            )
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "workspace-clear-none-json",
                "workspace",
            )
            smoke_json_assertions.assert_workspace_clear_json_result(
                result,
                errors,
                "workspace-clear-none-json",
                allow_none_state=True,
            )

        self.assertEqual(errors, [])

    def test_session_listing_use_and_forget_json_match_contracts(self) -> None:
        errors: list[str] = []
        seed_session = {
            "task_id": "task-wrapper-b",
            "effect_id": "effect-task-wrapper-b",
            "db": r"target\mvp\session.db",
            "output": r"target\mvp\output.txt",
            "owner_id": "safeclaw-mvp",
        }
        rows = [
            {
                "task_id": "task-wrapper-b",
                "effect_id": "effect-task-wrapper-b",
                "worker_state": "succeeded",
                "effect_status": "committed",
                "updated_at": "2026-04-13T00:00:00Z",
                "target_scope": "scope:target/mvp/output.txt",
                "lease_owner_id": "safeclaw-mvp",
            },
            {
                "task_id": "task-wrapper-a",
                "effect_id": "effect-task-wrapper-a",
                "worker_state": "succeeded",
                "effect_status": "committed",
                "updated_at": "2026-04-12T00:00:00Z",
                "target_scope": "scope:target/mvp/task-wrapper-a.txt",
                "lease_owner_id": "safeclaw-mvp",
            },
        ]

        with patched_state_root():
            exit_code, payload = capture_json_call(safeclaw_mvp.print_session, ["--json"])
            self.assertEqual(exit_code, 0)
            smoke_json_assertions.assert_json_null_result(
                payload,
                errors,
                "session-none-json",
                "session",
            )

            safeclaw_mvp.save_session(seed_session)

            exit_code, payload = capture_json_call(safeclaw_mvp.print_session, ["--json"])
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "session-json",
                "session",
            )
            smoke_json_assertions.assert_session_json_result(
                result,
                errors,
                "session-json",
                expected_task_id="task-wrapper-b",
            )

            with mock.patch.object(
                safeclaw_mvp,
                "load_heartbeat_config",
                return_value={"interval_ms": 10_000},
            ), mock.patch.object(
                safeclaw_mvp,
                "load_recent_tasks",
                return_value=rows,
            ):
                exit_code, payload = capture_json_call(
                    safeclaw_mvp.print_sessions,
                    ["--json"],
                )
                self.assertEqual(exit_code, 0)
                result = smoke_json_assertions.extract_json_result(
                    payload,
                    errors,
                    "sessions-json",
                    "sessions",
                )
                smoke_json_assertions.assert_sessions_json_result(
                    result,
                    errors,
                    "sessions-json",
                    expected_current_task_id="task-wrapper-b",
                    expected_previous_task_id="task-wrapper-a",
                )

                exit_code, payload = capture_json_call(
                    safeclaw_mvp.activate_session,
                    ["--index", "1", "--json"],
                )
                self.assertEqual(exit_code, 0)
                result = smoke_json_assertions.extract_json_result(
                    payload,
                    errors,
                    "use-json",
                    "use",
                )
                smoke_json_assertions.assert_use_json_result(
                    result,
                    errors,
                    "use-json",
                    expected_task_id="task-wrapper-a",
                    expected_source="index:1",
                )

            selected_session = safeclaw_mvp.load_session()
            self.assertIsNotNone(selected_session)
            self.assertEqual(selected_session["task_id"], "task-wrapper-a")
            self.assertEqual(selected_session["output"], r"target/mvp/task-wrapper-a.txt")

            exit_code, payload = capture_json_call(
                safeclaw_mvp.forget_session,
                ["--json"],
            )
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "forget-json",
                "forget",
            )
            smoke_json_assertions.assert_forget_json_result(
                result,
                errors,
                "forget-json",
            )

            exit_code, payload = capture_json_call(
                safeclaw_mvp.forget_session,
                ["--json"],
            )
            self.assertEqual(exit_code, 0)
            result = smoke_json_assertions.extract_json_result(
                payload,
                errors,
                "forget-none-json",
                "forget",
            )
            smoke_json_assertions.assert_forget_json_result(
                result,
                errors,
                "forget-none-json",
                allow_none_state=True,
            )

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
