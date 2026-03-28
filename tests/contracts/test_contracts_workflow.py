from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKFLOW_FILE = REPO_ROOT / '.github' / 'workflows' / 'contracts.yml'


class ContractsWorkflowTest(unittest.TestCase):
    def test_contracts_workflow_front_loads_ledger_policy_chain(self) -> None:
        text = WORKFLOW_FILE.read_text(encoding='utf-8')
        ordered_steps = [
            'Run ledger index manifest check',
            'Run ledger alignment check',
            'Run cross-file consistency check',
            'Run version consistency check',
            'Run structure completeness check',
            'Run scaffold layout check',
            'Run public docs alignment check',
            'Run naming lint',
            'Run contract tests',
        ]
        positions = [text.index(step_name) for step_name in ordered_steps]
        self.assertEqual(positions, sorted(positions))


if __name__ == '__main__':
    unittest.main()