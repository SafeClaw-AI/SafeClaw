from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.checks.spec_index import build_spec_index

SUPPORTED_TARGETS = ("rust", "python", "ts")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SafeClaw codegen 入口（Phase 0 空壳）",
    )
    parser.add_argument(
        "--target",
        choices=SUPPORTED_TARGETS,
        required=True,
        help="预留生成目标，目前只做契约装载校验。",
    )
    parser.add_argument(
        "--out-dir",
        default="generated",
        help="预留输出目录，当前不写入任何文件。",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    index = build_spec_index()

    print("SafeClaw codegen stub ready.")
    print(f"- target: {args.target}")
    print(f"- out_dir: {args.out_dir}")
    print(f"- specs_loaded: {len(index.documents)}")
    print("- status: Phase 0 协议层已接入，代码生成将在 M1 启用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
