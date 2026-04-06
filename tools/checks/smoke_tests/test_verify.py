"""Verify command smoke tests for CMD/PowerShell entry points."""

import os
import tempfile
from pathlib import Path

from .command_assertions import (
    assert_command_json_result,
    assert_command_json_error,
    assert_verify_json_result,
)
from .sitecustomize_factory import (
    write_smoke_verify_sitecustomize,
    build_smoke_pythonpath_env,
)


def append_root_verify_errors(errors: list[str]) -> None:
    assert_command_json_error(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "safeclaw.ps1",
            "verify",
            "--bogus",
            "--json",
        ],
        errors,
        "safeclaw-root-ps1-verify-invalid-json",
        "verify",
        expected_error_message_substring="unknown argument: --bogus",
    )
    with tempfile.TemporaryDirectory() as verify_mock_dir:
        write_smoke_verify_sitecustomize(Path(verify_mock_dir))
        verify_mock_env = build_smoke_pythonpath_env(Path(verify_mock_dir))
        previous_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = verify_mock_env["PYTHONPATH"]
        try:
            result = assert_command_json_result(
                ["cmd", "/c", "safeclaw.cmd", "verify", "--json"],
                errors,
                "safeclaw-root-cmd-verify-json",
                "verify",
            )
        finally:
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
    assert_verify_json_result(result, errors, "safeclaw-root-cmd-verify-json")
