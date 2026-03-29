from __future__ import annotations

import errno
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.mvp_state_guard import _process_is_running  # noqa: E402


class MvpStateGuardTest(unittest.TestCase):
    def test_permission_denied_still_means_process_is_alive(self) -> None:
        with patch(
            "tools.checks.mvp_state_guard.os.kill",
            side_effect=OSError(errno.EPERM, "permission denied"),
        ):
            self.assertTrue(_process_is_running(1234))

    def test_missing_process_returns_false(self) -> None:
        with patch(
            "tools.checks.mvp_state_guard.os.kill",
            side_effect=OSError(errno.ESRCH, "no such process"),
        ):
            self.assertFalse(_process_is_running(1234))


if __name__ == "__main__":
    unittest.main()
