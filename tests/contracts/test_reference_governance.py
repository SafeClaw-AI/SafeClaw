from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools.checks.reference_governance import (  # noqa: E402
    COMPLEXITY_RULE,
    FUNCTION_NONEMPTY_LINES_RULE,
    GovernanceThresholds,
    StructuralDebtEntry,
    StructuralDebtLedger,
    collect_structural_governance_errors,
    load_reference_governance_thresholds,
    load_structural_debt_ledger,
)


class ReferenceGovernanceTest(unittest.TestCase):
    def test_reference_governance_thresholds_are_stable(self) -> None:
        thresholds = load_reference_governance_thresholds()
        self.assertEqual(
            thresholds,
            GovernanceThresholds(
                function_nonempty_lines_limit=80,
                file_nonempty_lines_limit=1200,
                test_file_nonempty_lines_limit=2000,
                cyclomatic_complexity_limit=10,
                core_business_cyclomatic_complexity_limit=7,
            ),
        )

    def test_structural_debt_ledger_core_paths_are_stable(self) -> None:
        ledger = load_structural_debt_ledger()
        self.assertEqual(
            ledger.core_business_paths,
            (
                "safeclaw-core/",
                "safeclaw-sqlite/",
                "tools/mvp/",
                "modules/",
            ),
        )

    def test_structural_governance_passes_current_baseline(self) -> None:
        self.assertEqual(collect_structural_governance_errors(), [])

    def test_structural_governance_requires_ledger_for_new_function_size_violation(self) -> None:
        thresholds = GovernanceThresholds(
            function_nonempty_lines_limit=2,
            file_nonempty_lines_limit=999,
            test_file_nonempty_lines_limit=999,
            cyclomatic_complexity_limit=99,
            core_business_cyclomatic_complexity_limit=99,
        )
        ledger = StructuralDebtLedger(core_business_paths=(), entries=())

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source_file = repo_root / "src" / "sample.py"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text(
                "def sample():\n"
                "    value = 1\n"
                "    value += 1\n"
                "    return value\n",
                encoding="utf-8",
            )

            errors = collect_structural_governance_errors(
                repo_root=repo_root,
                thresholds=thresholds,
                structural_debt_ledger=ledger,
                today=date(2026, 4, 7),
            )

        self.assertEqual(
            errors,
            [
                "结构性债务未入账: src/sample.py -> 单函数非空行 "
                "(count=1; max=4; symbol=sample; line=1，目标 ≤2)"
            ],
        )

    def test_structural_governance_rejects_expired_debt_entry(self) -> None:
        thresholds = GovernanceThresholds(
            function_nonempty_lines_limit=2,
            file_nonempty_lines_limit=999,
            test_file_nonempty_lines_limit=999,
            cyclomatic_complexity_limit=99,
            core_business_cyclomatic_complexity_limit=99,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source_file = repo_root / "src" / "sample.py"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text(
                "def sample():\n"
                "    value = 1\n"
                "    value += 1\n"
                "    return value\n",
                encoding="utf-8",
            )

            ledger = StructuralDebtLedger(
                core_business_paths=(),
                entries=(
                    StructuralDebtEntry(
                        object_id="src/sample.py",
                        rule_key=FUNCTION_NONEMPTY_LINES_RULE,
                        current_value="count=1; max=4; symbol=sample; line=1",
                        target_value="≤2",
                        owner="tests-owner",
                        due_date=date(2026, 4, 6),
                        can_split="是",
                        reason="临时测试条目",
                    ),
                ),
            )
            errors = collect_structural_governance_errors(
                repo_root=repo_root,
                thresholds=thresholds,
                structural_debt_ledger=ledger,
                today=date(2026, 4, 7),
            )

        self.assertEqual(
            errors,
            ["结构性债务已逾期: src/sample.py -> 单函数非空行 (due 2026-04-06)"],
        )

    def test_structural_governance_rejects_stale_ledger_entry(self) -> None:
        thresholds = GovernanceThresholds(
            function_nonempty_lines_limit=80,
            file_nonempty_lines_limit=999,
            test_file_nonempty_lines_limit=999,
            cyclomatic_complexity_limit=10,
            core_business_cyclomatic_complexity_limit=7,
        )
        ledger = StructuralDebtLedger(
            core_business_paths=(),
            entries=(
                StructuralDebtEntry(
                    object_id="src/clean.py",
                    rule_key=COMPLEXITY_RULE,
                    current_value="count=1; max=12; symbol=sample; line=1; limit=10",
                    target_value="≤10",
                    owner="tests-owner",
                    due_date=date(2026, 7, 7),
                    can_split="是",
                    reason="临时测试条目",
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source_file = repo_root / "src" / "clean.py"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text(
                "def sample(flag: bool) -> int:\n"
                "    return 1 if flag else 0\n",
                encoding="utf-8",
            )

            errors = collect_structural_governance_errors(
                repo_root=repo_root,
                thresholds=thresholds,
                structural_debt_ledger=ledger,
                today=date(2026, 4, 7),
            )

        self.assertEqual(
            errors,
            ["结构性债务台账未清零: src/clean.py -> 圈复杂度"],
        )
