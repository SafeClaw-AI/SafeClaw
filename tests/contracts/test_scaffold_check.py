from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_scaffold import (  # noqa: E402
    ALLOWED_HIDDEN_ROOT_ENTRIES,
    FORBIDDEN_NAME_TOKENS,
    LEGACY_REQUIRED_STATES,
    REFERENCE_REQUIRED_FILES,
    ROOT_TEXT_POLICY_FILES,
    TMP_DISALLOWED_PREFIXES,
    collect_ledger_scaffold_errors,
    collect_reference_guardrail_errors,
    load_locked_root_entries,
)


class ScaffoldCheckTest(unittest.TestCase):
    def test_legacy_required_states_are_stable(self) -> None:
        self.assertEqual(LEGACY_REQUIRED_STATES, {"legacy-only", "dual-readable"})

    def test_reference_required_files_are_stable(self) -> None:
        expected = [
            "docs/reference/01-反屎山工程规范.md",
        ]
        self.assertEqual(
            [path.relative_to(REPO_ROOT).as_posix() for path in REFERENCE_REQUIRED_FILES],
            expected,
        )

    def test_root_text_policy_files_are_stable(self) -> None:
        self.assertEqual(
            [path.relative_to(REPO_ROOT).as_posix() for path in ROOT_TEXT_POLICY_FILES],
            [".gitattributes"],
        )

    def test_forbidden_name_tokens_are_stable(self) -> None:
        self.assertEqual(FORBIDDEN_NAME_TOKENS, ("最终版", "临时版", "new2", "test1"))

    def test_allowed_hidden_root_entries_include_gitattributes(self) -> None:
        self.assertEqual(ALLOWED_HIDDEN_ROOT_ENTRIES, {".github", ".gitattributes", ".gitignore"})

    def test_tmp_disallowed_prefixes_are_stable(self) -> None:
        self.assertEqual(TMP_DISALLOWED_PREFIXES, ("round-log-",))

    def test_locked_root_entries_cover_current_baseline(self) -> None:
        locked_root_dirs, locked_root_files = load_locked_root_entries()
        governed_root_dirs = {
            path.name
            for path in REPO_ROOT.iterdir()
            if path.is_dir()
            and (not path.name.startswith(".") or path.name in ALLOWED_HIDDEN_ROOT_ENTRIES)
        }
        governed_root_files = {
            path.name
            for path in REPO_ROOT.iterdir()
            if path.is_file()
            and not path.name.startswith(".")
        }
        self.assertTrue(governed_root_dirs.issubset(locked_root_dirs))
        self.assertTrue(governed_root_files.issubset(locked_root_files))

    def test_reference_guardrails_pass_current_baseline(self) -> None:
        self.assertEqual(collect_reference_guardrail_errors(), [])

    def test_ledger_scaffold_policy_passes_current_baseline(self) -> None:
        self.assertEqual(collect_ledger_scaffold_errors(), [])


if __name__ == "__main__":
    unittest.main()
