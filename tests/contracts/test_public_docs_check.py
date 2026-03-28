from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.check_public_docs import collect_reference_rebaseline_errors  # noqa: E402


class PublicDocsCheckTest(unittest.TestCase):
    def test_reference_rebaseline_doc_passes_current_baseline(self) -> None:
        self.assertEqual(collect_reference_rebaseline_errors(), [])


if __name__ == "__main__":
    unittest.main()