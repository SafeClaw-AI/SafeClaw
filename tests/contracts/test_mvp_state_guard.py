from __future__ import annotations

import errno
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.checks.mvp_state_guard as mvp_state_guard  # noqa: E402
from tools.checks.mvp_state_guard import (  # noqa: E402
    WINDOWS_STILL_ACTIVE,
    _process_is_running,
    _process_is_running_with_signal,
    _process_is_running_with_winapi,
)


class MvpStateGuardTest(unittest.TestCase):
    def test_permission_denied_still_means_process_is_alive(self) -> None:
        with patch(
            "tools.checks.mvp_state_guard.os.kill",
            side_effect=OSError(errno.EPERM, "permission denied"),
        ):
            self.assertTrue(_process_is_running_with_signal(1234))

    def test_missing_process_returns_false(self) -> None:
        with patch(
            "tools.checks.mvp_state_guard.os.kill",
            side_effect=OSError(errno.ESRCH, "no such process"),
        ):
            self.assertFalse(_process_is_running_with_signal(1234))

    def test_windows_invalid_parameter_returns_false(self) -> None:
        with patch("tools.checks.mvp_state_guard.WINDOWS_KERNEL32") as kernel32, patch(
            "tools.checks.mvp_state_guard.ctypes.get_last_error",
            return_value=87,
        ):
            kernel32.OpenProcess.return_value = 0
            self.assertFalse(_process_is_running_with_winapi(1234))

    def test_windows_still_active_process_returns_true(self) -> None:
        with patch("tools.checks.mvp_state_guard.WINDOWS_KERNEL32") as kernel32:
            kernel32.OpenProcess.return_value = 1

            def fill_exit_code(_handle: int, exit_code_ref: object) -> int:
                exit_code_ref._obj.value = WINDOWS_STILL_ACTIVE
                return 1

            kernel32.GetExitCodeProcess.side_effect = fill_exit_code
            self.assertTrue(_process_is_running_with_winapi(1234))
            kernel32.CloseHandle.assert_called_once_with(1)

    def test_acquire_lock_recovers_stale_holder_file(self) -> None:
        target_root = REPO_ROOT / "target"
        target_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target_root) as temp_dir:
            repo_root = Path(temp_dir)
            state_root = repo_root / "target" / "mvp"
            lock_file = state_root / ".wrapper-check.lock"
            state_root.mkdir(parents=True, exist_ok=True)
            lock_file.write_text("check_tooling_smoke pid=999999", encoding="utf-8")
            with patch.object(mvp_state_guard, "REPO_ROOT", repo_root), patch.object(
                mvp_state_guard,
                "STATE_ROOT",
                state_root,
            ), patch.object(mvp_state_guard, "LOCK_FILE", lock_file), patch.object(
                mvp_state_guard,
                "_process_is_running",
                return_value=False,
            ):
                with mvp_state_guard.acquire_mvp_state_lock("test_mvp_state_guard"):
                    self.assertTrue(lock_file.exists())
                    holder = lock_file.read_text(encoding="utf-8").strip()
                    self.assertIn("test_mvp_state_guard", holder)
                    self.assertIn(f"pid={os.getpid()}", holder)
                self.assertFalse(lock_file.exists())

    def test_acquire_lock_reuses_existing_lock_env_without_rewriting_file(self) -> None:
        target_root = REPO_ROOT / "target"
        target_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target_root) as temp_dir:
            repo_root = Path(temp_dir)
            state_root = repo_root / "target" / "mvp"
            lock_file = state_root / ".wrapper-check.lock"
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop(mvp_state_guard.LOCK_ENV, None)
                with patch.object(mvp_state_guard, "REPO_ROOT", repo_root), patch.object(
                    mvp_state_guard,
                    "STATE_ROOT",
                    state_root,
                ), patch.object(mvp_state_guard, "LOCK_FILE", lock_file):
                    with mvp_state_guard.acquire_mvp_state_lock("outer_lock_check"):
                        self.assertTrue(lock_file.exists())
                        outer_holder = lock_file.read_text(encoding="utf-8").strip()
                        self.assertIn("outer_lock_check", outer_holder)
                        self.assertEqual(
                            os.environ.get(mvp_state_guard.LOCK_ENV),
                            "outer_lock_check",
                        )
                        with mvp_state_guard.acquire_mvp_state_lock("inner_lock_check"):
                            self.assertTrue(lock_file.exists())
                            self.assertEqual(
                                lock_file.read_text(encoding="utf-8").strip(),
                                outer_holder,
                            )
                            self.assertEqual(
                                os.environ.get(mvp_state_guard.LOCK_ENV),
                                "outer_lock_check",
                            )
                            self.assertEqual(list(state_root.iterdir()), [lock_file])
                        self.assertEqual(
                            lock_file.read_text(encoding="utf-8").strip(),
                            outer_holder,
                        )
                        self.assertEqual(
                            os.environ.get(mvp_state_guard.LOCK_ENV),
                            "outer_lock_check",
                        )
                    self.assertFalse(lock_file.exists())
                    self.assertNotIn(mvp_state_guard.LOCK_ENV, os.environ)


if __name__ == "__main__":
    unittest.main()
