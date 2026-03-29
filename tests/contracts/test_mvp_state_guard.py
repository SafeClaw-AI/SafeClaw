from __future__ import annotations

import errno
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


if __name__ == "__main__":
    unittest.main()
